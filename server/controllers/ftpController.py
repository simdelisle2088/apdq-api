from ftplib import FTP
import os
from typing import BinaryIO, Tuple
from datetime import datetime
import asyncio
from functools import partial

class FTPManager:
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password
        self.base_path = "apdq"  # Base directory on FTP server

    def connect(self) -> FTP:
        # Connect and login using positional arguments as required by ftplib
        ftp = FTP(self.host)
        ftp.login(self.user, self.password)
        return ftp

    def _ensure_directory_exists(self, ftp: FTP, path: str):
        """
        Navigate to a directory, creating it if it doesn't exist.
        This handles both absolute and relative paths.
        """
        # Start from root
        ftp.cwd('/')
        
        # Split path and navigate/create each directory
        for directory in path.split('/'):
            if directory:  # Skip empty parts
                try:
                    ftp.cwd(directory)
                except:
                    ftp.mkd(directory)
                    ftp.cwd(directory)

    def _upload_file_sync(self, file, unique_filename, target_dir, server_path):
        """
        Synchronously upload a file to the FTP server.
        """
        ftp = self.connect()
        try:
            # First, go to root directory
            ftp.cwd('/')
            
            # Ensure the base directory exists
            full_path = f"{self.base_path}/{target_dir}"
            self._ensure_directory_exists(ftp, full_path)
            
            # Make sure we're in the right directory
            ftp.cwd(f"/{full_path}")
            
            # Reset file pointer and upload
            file.seek(0)
            ftp.storbinary(f'STOR {unique_filename}', file)
            
            # Get the file size
            file_size = ftp.size(unique_filename)
            
            return server_path, file_size
            
        except Exception as e:
            print(f"FTP Upload Error: {str(e)}")  # Add debugging
            raise Exception(f"Failed to upload file: {str(e)}")
        finally:
            ftp.quit()

    async def upload_file(self, file: BinaryIO, filename: str, file_type: str) -> Tuple[str, int]:
        """
        Asynchronously upload a file to the FTP server.
        """
        if file_type not in ['pdf', 'image']:
            raise ValueError("file_type must be either 'pdf' or 'image'")

        # Create unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        
        # Set target directory based on file type
        target_dir = 'pdf' if file_type == 'pdf' else 'images'
        server_path = f"{self.base_path}/{target_dir}/{unique_filename}"

        # Run FTP operations in thread pool
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None,
                partial(self._upload_file_sync, file, unique_filename, target_dir, server_path)
            )
        except Exception as e:
            print(f"Upload Error: {str(e)}")  # Add debugging
            raise Exception(f"Failed to upload file: {str(e)}")
        
    async def delete_file(self, file_path: str) -> bool:
       
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None,
                partial(self._delete_file_sync, file_path)
            )
        except Exception as e:
            raise Exception(f"Failed to delete file: {str(e)}")

    def _delete_file_sync(self, file_path: str) -> bool:
        ftp = self.connect()
        try:
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            
            ftp.cwd(directory)
            ftp.delete(filename)
            return True
        finally:
            ftp.quit()