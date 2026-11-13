import requests
import json
import logging
from typing import Optional, Dict, Any, List

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger("EagleClient")

class EagleClient:
    def __init__(self, base_url: str = "http://localhost:41595"):
        self.base_url = base_url.rstrip("/")
        self.folder_cache = {}
        
    def request(self, path, payload=None):
        response = requests.get(self.base_url + path, timeout=10) if payload is None else requests.post(self.base_url + path, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success":
            raise ValueError("Eagle chưa xác nhận thành công")
        return data.get("data")

    def is_connected(self) -> bool:
        """Check if Eagle is running and listening on localhost:41595"""
        try:
            res = requests.get(f"{self.base_url}/api/application/info", timeout=1.5)
            if res.status_code == 200:
                data = res.json()
                return data.get("status") == "success"
        except Exception:
            pass
        return False

    def get_info(self) -> Optional[Dict[str, Any]]:
        """Retrieve Eagle application and library details"""
        try:
            res = requests.get(f"{self.base_url}/api/application/info", timeout=2.0)
            if res.status_code == 200:
                return res.json().get("data", {})
        except Exception as e:
            logger.warning(f"Cannot get Eagle info: {e}")
        return None

    def get_library_info(self) -> Optional[Dict[str, Any]]:
        """Retrieve Eagle active library information"""
        try:
            return self.request('/api/library/info')
        except Exception as e:
            logger.warning(f"Cannot get Eagle library info: {e}")
            return None

    def get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Find an existing folder by name or create a new one, return folderId"""
        if folder_name in self.folder_cache:
            return self.folder_cache[folder_name]

        try:
            # 1. Search existing folders
            res = requests.get(f"{self.base_url}/api/folder/list", timeout=3.0)
            if res.status_code == 200:
                folders = res.json().get("data", [])
                
                def search_tree(nodes):
                    for node in nodes:
                        if node.get("name") == folder_name:
                            return node.get("id")
                        sub = node.get("children", [])
                        if sub:
                            found = search_tree(sub)
                            if found:
                                return found
                    return None

                found_id = search_tree(folders)
                if found_id:
                    self.folder_cache[folder_name] = found_id
                    return found_id

            # 2. Create if not found
            payload = {"folderName": folder_name}
            if parent_id:
                payload["parent"] = parent_id
                
            create_res = requests.post(f"{self.base_url}/api/folder/create", json=payload, timeout=3.0)
            if create_res.status_code == 200:
                new_folder = create_res.json().get("data", {})
                new_id = new_folder.get("id")
                if new_id:
                    self.folder_cache[folder_name] = new_id
                    logger.info(f"Created folder '{folder_name}' in Eagle (id={new_id})")
                    return new_id
        except Exception as e:
            logger.error(f"Error handling folder '{folder_name}': {e}")
            
        return None

    def add_from_url(
        self,
        url: str,
        name: str,
        tags: Optional[List[str]] = None,
        annotation: str = "",
        rating: int = 0,
        folder_id: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Add media directly into Eagle from a remote URL"""
        try:
            payload = {
                "url": url,
                "name": name,
                "tags": tags or [],
                "annotation": annotation,
                "rating": max(0, min(5, rating))
            }
            if folder_id:
                payload["folderId"] = folder_id
            if headers:
                payload["headers"] = headers

            res = requests.post(f"{self.base_url}/api/item/addFromURL", json=payload, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "success":
                    logger.info(f"Successfully added to Eagle: {name}")
                    return data
                else:
                    logger.warning(f"Eagle rejected URL item: {data}")
            else:
                logger.error(f"HTTP error adding to Eagle: {res.status_code}")
        except Exception as e:
            logger.error(f"Failed to add URL to Eagle ({url[:60]}...): {e}")
        return None

    def add_from_path(
        self,
        file_path: str,
        name: str,
        tags: Optional[List[str]] = None,
        annotation: str = "",
        rating: int = 0,
        folder_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Add local file into Eagle library"""
        try:
            payload = {
                "path": file_path,
                "name": name,
                "tags": tags or [],
                "annotation": annotation,
                "rating": max(0, min(5, rating))
            }
            if folder_id:
                payload["folderId"] = folder_id

            res = requests.post(f"{self.base_url}/api/item/addFromPath", json=payload, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "success":
                    logger.info(f"Successfully added local file to Eagle: {name}")
                    return data
        except Exception as e:
            logger.error(f"Failed to add local file to Eagle: {e}")
        return None
