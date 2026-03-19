#local database

import sqlite3

class DatabaseManager:
    def __init__(self,db_path="vault.db"):
        
        self.conn = sqlite3.connect(db_path,check_same_thread=False) #allow access from multiple threads
        self.create_tables()
        
    def create_tables(self):
        # Create the vault table if it doesn't exist
        cursor = self.conn.cursor()
        #Folder table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL
            )
        ''')
        #Image tag table
        #Unique tags
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL,
                tag TEXT NOT NULL,
                UNIQUE(image_path,tag)
            )           
        ''')
        
        self.conn.commit()    
    
    def add_tag(self,image_path,tag):
        cursor= self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO tags (image_path,tag) VALUES (?,?)",(image_path,tag))
        self.conn.commit()
    
    def get_tags_for_image(self,image_path):
        cursor = self.conn.cursor()
        cursor.execute("SELECT tag FROM tags WHERE image_path = ?",(image_path,))
        #return list of tuple [('hand',),('face',)]
        return [row[0] for row in cursor.fetchall()]
    
    def add_folder(self,name,path):
        cursor = self.conn.cursor()
        #Insert the folder into the database, ignoring duplicates based on the unique path
        cursor.execute("INSERT OR IGNORE INTO folders (name, path) VALUES (?, ?)", (name, path))
        self.conn.commit()
    
    def get_folders(self):
        #Retrieve all folders from the database
        cursor = self.conn.cursor()    
        cursor.execute("SELECT name, path FROM folders")
        #return tuples of (name, path) for all folders in the database
        return cursor.fetchall()
    
    def delete_folder(self,path):
        cursor = self.conn.cursor()
        #Delete the folder from the database based on the unique path
        cursor.execute("DELETE FROM folders WHERE path = ?", (path,))
        self.conn.commit()
        
    def search_images_by_tag(self,folder_path,search_term):
        cursor = self.conn.cursor()
         #use like operator to match search term
        query="""
            SELECT DISTINCT image_path
            FROM tags
            WHERE image_path LIKE ? AND tag LIKE ?
        """
        
        #append % to the folder path so it matches a file inside that folder
        folder_wildcard = f"{folder_path}%"   
        search_wildcard=f"{search_term}%"
        
        cursor.execute(query,(folder_wildcard,search_wildcard))
        
        #return list of matching file paths
        return [row[0] for row in cursor.fetchall()]
    
    #for auto complete search
    def get_unique_tags(self):
        cursor=self.conn.cursor()
        #get every unique tag that exists
        cursor.execute("SELECT DISTINCT tag FROM tags")
        return [row[0] for row in cursor.fetchall()]
    
    def global_search_by_tag(self,search_term):
        cursor=self.conn.cursor()
        search_wildcard=f"%{search_term}%"
        
        #look across entire DB
        query="""
           SELECT DISTINCT image_path
           FROM tags
           WHERE tag LIKE ?
        """
        cursor.execute(query,(search_wildcard,))
        return [row[0] for row in cursor.fetchall()]   
    
    #save hundreds of tags in a single operation instead of one by one
    def batch_add_tags(self,tag_data_list):
        cursor = self.conn.cursor()
        if not tag_data_list:
            return
        
        self.conn.execute("BEGIN TRANSACTION")
        try:
            for image_path, tags in tag_data_list:
                for tag in tags:
                    cursor.execute("INSERT OR IGNORE INTO tags (image_path,tag) VALUES (?,?)", (image_path, tag))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Batch DB save failed: {e}")
    
    def rename_folder(self, old_path, new_path, new_name):
        cursor = self.conn.cursor()
        self.conn.execute("BEGIN TRANSACTION")
        try:
            #update the master folder table
            cursor.execute("UPDATE folders SET name = ?, path = ? WHERE path = ?", (new_name, new_path, old_path))
            
            #find all tags that belong to images inside this folder and update their paths
            #use SQLite REPLACE function to swap the base directory
            cursor.execute("""
                UPDATE tags 
                SET image_path = REPLACE(image_path, ?, ?) 
                WHERE image_path LIKE ?
            """, (old_path, new_path, old_path + '%'))
            
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Failed to rename folder in DB: {e}")        
    #Replace all images existing tags for new ones
    def update_image_tags(self, image_path, new_tags_list):
        
        cursor = self.conn.cursor()
        self.conn.execute("BEGIN TRANSACTION")
        try:
            #remove the old tags for this specific image
            cursor.execute("DELETE FROM tags WHERE image_path = ?", (image_path,))
            
            #insert the new ones
            for tag in new_tags_list:
                cursor.execute("INSERT INTO tags (image_path, tag) VALUES (?, ?)", (image_path, tag))
                
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Failed to update tags in DB: {e}")        