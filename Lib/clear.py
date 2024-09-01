
#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                             ________
#?                            / ____/ /__  ____ ______
#?                           / /   / / _ \/ __ `/ ___/
#?                          / /___/ /  __/ /_/ / /    
#?                          \____/_/\___/\__,_/_/     
#?                          
#?
#? Name:        Failures.py
#? Purpose:     Clear all tempo files.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? -------------------------------------------------------------------------------  
#                                      
import os


current_directory   =   os.getcwd()                                                                                                                                                              
folder_paths        =  [(os.path.join(current_directory, "D:/4 WORKSPACE/FASTER/FASTER/RES/")).replace("\\", "/")  
                       ]          

def delete_files_in_folder(folder_path):
    if not os.path.isdir(folder_path):
        print("Error: The provided path is not a directory.")
        return
    files = os.listdir(folder_path)
    for file_name in files:
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

def clear_all():
    for folder_path in folder_paths:
        delete_files_in_folder(folder_path)

#? -------------------------------------------------------------------------------                                       
