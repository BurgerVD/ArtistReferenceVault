import os
import sys
import time
import traceback
import queue
import csv
import gc
import numpy as np
from PIL import Image

import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PyQt6.QtCore import QThread, pyqtSignal

from huggingface_hub.utils.tqdm import disable_progress_bars
disable_progress_bars()


class AITaggerWorker(QThread):
    tags_generated = pyqtSignal(str, list)
    engine_ready = pyqtSignal()
    error_signal = pyqtSignal(str)
    queue_updated = pyqtSignal(int)
    engine_loaded = pyqtSignal()
    engine_unloaded = pyqtSignal()
    
    
    
    def __init__(self):
        super().__init__()

        self.inbox = queue.Queue()
        self.is_running = True

        self.session = None
        self.model_path = ""
        self.tags_vocab = []

        self.sess_options = ort.SessionOptions()

        #Idle system 
        self.last_activity = time.time()
        self.IDLE_TIMEOUT = 60 #1min
        self.max_tags = 12
    
    #ENGINE LIFECYCLE
    
    def create_session(self, providers):
        return ort.InferenceSession(
            self.model_path,
            sess_options=self.sess_options,
            providers=providers
        )

    def load_engine(self):
        print("Loading ONNX inference engine...")

        try:
            print("Attempting GPU (DirectML)...")

            self.session = self.create_session(['DmlExecutionProvider'])

            if 'DmlExecutionProvider' not in self.session.get_providers():
                raise RuntimeError("DirectML not active")

            print("SUCCESS: Running on GPU")

        except Exception as e:
            print(f"GPU failed, switching to CPU: {e}")

            os.environ["OMP_NUM_THREADS"] = "3"
            self.sess_options.intra_op_num_threads = 3
            self.sess_options.inter_op_num_threads = 3
            self.sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

            try:
                self.session = self.create_session(['CPUExecutionProvider'])
                print("SUCCESS: Running on CPU")
            except Exception as e2:
                print(f"CRITICAL: Failed to load CPU session: {e2}")
                self.session = None
        if self.session is not None:
            self.engine_loaded.emit()
        
        
    def unload_engine(self):
        try:
            if self.session is not None:
                print("Unloading AI model from memory...")
                del self.session
                self.session = None
                gc.collect()
                print("Model unloaded.")
                self.engine_unloaded.emit()

        except Exception as e:
            print(f"Unload error: {e}")

    def ensure_session(self):
        """
        Ensures session exists before inference.
        Returns True if ready, False if failed.
        """
        if self.session is None:
            print("Reloading AI model...")
            self.load_engine()

        return self.session is not None

    
    #THREAD ENTRY
    
    def run(self):
       
        try:
            print("Initializing AI Engine...")

            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))

            local_model_path = os.path.join(app_dir, "ai_model", "model.onnx")
            local_tags_path = os.path.join(app_dir, "ai_model", "selected_tags.csv")

            if os.path.exists(local_model_path) and os.path.exists(local_tags_path):
                print("Using bundled model.")
                self.model_path = local_model_path
                tags_path = local_tags_path
            else:
                print("Downloading model...")
                repo_id = "SmilingWolf/wd-v1-4-moat-tagger-v2"
                self.model_path = hf_hub_download(repo_id, "model.onnx")
                tags_path = hf_hub_download(repo_id, "selected_tags.csv")

            print("Loading tags...")
            with open(tags_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    self.tags_vocab.append(row[1])

            self.load_engine()
            self.engine_ready.emit()

        except Exception:
            error_msg = traceback.format_exc()

            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))

            log_path = os.path.join(app_dir, "Vault_Crash_Log.txt")
            with open(log_path, "a") as f:
                f.write(f"ENGINE FAILED:\n{error_msg}\n\n")

            return

      
        #MAIN LOOP
        
        while self.is_running:
            image_path = None

            try:
                image_path = self.inbox.get(timeout=1.0)

                if image_path == "STOP_ENGINE":
                    break

                self.last_activity = time.time()

                #Skip videos and non-static images so PIL doesn't crash
                ext = os.path.splitext(image_path)[1].lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                    print(f"Skipping AI tagging for video format: {os.path.basename(image_path)}")
                    continue
                
                #Ensure model is loaded BEFORE doing anything
                if not self.ensure_session():
                    print("Model unavailable. Skipping image.")
                    continue

                if os.path.getsize(image_path) == 0:
                    print(f"Skipping corrupt file: {image_path}")
                    continue

                #IMAGE PREPROCESSING
                image = Image.open(image_path).convert("RGB")

                max_dim = max(image.size)
                padded = Image.new("RGB", (max_dim, max_dim), (255, 255, 255))
                padded.paste(image, (
                    (max_dim - image.size[0]) // 2,
                    (max_dim - image.size[1]) // 2
                ))

                image_resized = padded.resize((448, 448), Image.Resampling.LANCZOS)

                image_array = np.array(image_resized, dtype=np.float32)
                image_array = image_array[:, :, ::-1]
                image_array = np.expand_dims(image_array, axis=0)

                #INFERENCE
                #Double safety check
                if self.session is None:
                    continue

                input_name = self.session.get_inputs()[0].name
                raw_outputs = self.session.run(None, {input_name: image_array})[0]

                probs = np.array(raw_outputs[0])
                THRESHOLD = 0.35

                valid_tags = []
                for i in range(4, len(probs)):
                    if probs[i] > THRESHOLD:
                        valid_tags.append((probs[i], self.tags_vocab[i]))

                valid_tags.sort(key=lambda x: x[0], reverse=True)

                generated_tags = [
                    tag.replace('_', ' ')
                    for _, tag in valid_tags[:self.max_tags]
                ]

                if generated_tags:
                    self.tags_generated.emit(image_path, generated_tags)
                    print(f"Tagged {os.path.basename(image_path)}: {generated_tags}")

            except queue.Empty:
                pass

            except Exception as e:
                error_msg = traceback.format_exc()

                if getattr(sys, 'frozen', False):
                    app_dir = os.path.dirname(sys.executable)
                else:
                    app_dir = os.path.dirname(os.path.abspath(__file__))

                log_path = os.path.join(app_dir, "Vault_Crash_Log.txt")
                with open(log_path, "a") as f:
                    f.write(f"Crash on {image_path}:\n{error_msg}\n\n")

                print(f"Error processing {image_path}: {e}")

            finally:
                if image_path and image_path != "STOP_ENGINE":
                    self.inbox.task_done()
                    self.queue_updated.emit(self.inbox.qsize())
                    time.sleep(0.01)

          
            #IDLE CHECK
           
            if self.session is not None:
                idle_time = time.time() - self.last_activity

                if idle_time > self.IDLE_TIMEOUT:
                    print("Idle timeout reached. Unloading model...")
                    self.unload_engine()

   
    #API
   
    def queue_image(self, image_path):
        self.inbox.put(image_path)
        self.queue_updated.emit(self.inbox.qsize())
        #Auto-wake the thread if it receives an image while disabled
        if not self.isRunning():
            self.start()
    def stop_engine(self):
        self.is_running = False
        self.inbox.put("STOP_ENGINE")
        self.wait()
        
    