import requests
import random
import time
from typing import Optional, Dict, Any


class FHIRClient:
    def __init__(self, base_url: str = "http://34.170.56.151:8080/fhir/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/fhir+json"})
        self.verify_connection()

    def verify_connection(self):
        try:
            response = self.session.get(f"{self.base_url}metadata")
            response.raise_for_status()
            print("Connected to FHIR server successfully!")
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to FHIR server: {e}")
            raise

    def create_resource(self, resource_type: str, resource_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a resource on the FHIR server.
        :param resource_type: The FHIR resource type (e.g., 'Patient', 'Observation').
        :param resource_data: The resource data in FHIR JSON format.
        :return: The created resource or None if there was an error.
        """
        url = f"{self.base_url}{resource_type}"
        try:
            response = self.session.post(url, json=resource_data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating resource: {e}")
            return None

    def get_resource(self, resource_type: str, resource_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a resource from the FHIR server.
        :param resource_type: The FHIR resource type (e.g., 'Patient').
        :param resource_id: The ID of the resource to retrieve.
        :return: The resource data or None if there was an error.
        """
        url = f"{self.base_url}{resource_type}/{resource_id}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving resource: {e}")
            return None

    def search_resources(self, resource_type: str, search_params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Search for resources on the FHIR server.
        :param resource_type: The FHIR resource type (e.g., 'Patient').
        :param search_params: A dictionary of search parameters.
        :return: The search results or None if there was an error.
        """
        url = f"{self.base_url}{resource_type}"
        try:
            response = self.session.get(url, params=search_params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error searching resources: {e}")
            return None

    def delete_resource(self, resource_type: str, resource_id: str) -> bool:
        """
        Delete a resource from the FHIR server.
        :param resource_type: The FHIR resource type (e.g., 'Patient').
        :param resource_id: The ID of the resource to delete.
        :return: True if deletion was successful, False otherwise.
        """
        url = f"{self.base_url}{resource_type}/{resource_id}"
        try:
            response = self.session.delete(url)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error deleting resource: {e}")
            return False
