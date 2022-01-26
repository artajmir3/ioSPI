"""Module to upload data to OSF.io generated by simSPI TEM Simulator."""
from pathlib import Path
from typing import Optional, Type

import requests
from simSPI.simSPI import tem


class TEMUpload:
    """Class to upload data to OSF.io generated by simSPI TEM Simulator.

    Parameters
    ----------
    token : str
        Personal token from OSF.io with access to cryoEM dataset.
    data_node_guid : str, default = "24htr"
        OSF GUID of data node that houses dataset.

    Attributes
    ----------
    headers : dict of type str:str
        Headers containing authorisation token for requests.
    base_url : str
        OSF.io API url base.
    data_node_guid : str
        OSF GUID of data node that houses dataset.

    See Also
    --------
    OSF API documentation : https://developer.osf.io/
    """

    def __init__(self, token: str, data_node_guid: str = "24htr") -> None:

        self.headers = {"Authorization": f"Bearer {token}"}
        self.base_url = "https://api.osf.io/v2/"

        requests.get(self.base_url, headers=self.headers).raise_for_status()

        self.data_node_guid = data_node_guid

    def upload_dataset_from_tem(self, tem_sim: Type[tem.TEMSimulator]) -> bool:
        """Upload particle stacks and metadata as labelled datsets to OSF.io.

        Parameters
        ----------
        tem_sim : TEMSimulator
        Instance of temSimulator containing local upload file paths.

        Returns
        -------
        bool
            True if all uploads successful, False otherwise.
        """
        dataset_label = (
            tem_sim.path_dict["pdb_keyword"] + tem_sim.path_dict["micrograph_keyword"]
        )
        molecule_label = tem_sim.path_dict["pdb_keyword"]
        molecule_guid = self.get_molecule_guid(molecule_label)
        dataset_guid = self.post_child_node(
            molecule_guid, dataset_label, tags=self.generate_tags_from_tem(tem_sim)
        )

        upload_file_paths = [tem_sim.output_path_dict["h5_file"]]
        return self.post_files(dataset_guid, upload_file_paths)

    def get_molecule_guid(self, molecule_label: str) -> str:
        """Get GUID of node housing data for given molecule.

        If no existing node with given label is found, a
        new one is created.


        Parameters
        ----------
        molecule_label:str
            Molecule ID from PDB or EMDB used for generating data.

        Returns
        -------
            GUID of molecule node on OSF.io

        See Also
        --------
        Protein Data Bank(PDB) : https://www.rcsb.org/
        EM DataR esouce(EMDB) : https://www.emdataresource.org/
        """
        existing_molecules = self.get_existing_molecules()
        if molecule_label not in existing_molecules:
            return self.post_child_node(self.data_node_guid, molecule_label)
        return existing_molecules[molecule_label]

    @staticmethod
    def generate_tags_from_tem(tem_wrapper: Type[tem.TEMSimulator]) -> list[str]:
        """Generate a list of tags from simulator parameters.

        Parameters
        ----------
        tem_wrapper : TEMSimulator
            Instance of TEMSimulator with simulator parameters.

        Returns
        -------
        list[str]
            List of tags for dataset.
        """
        placeholder_values = tem_wrapper.sim_dict
        return list(placeholder_values.values())

    def post_child_node(
        self, parent_guid: str, title: str, tags: Optional[str] = None
    ) -> str:
        """Create a new child node in OSF.io.

        Parameters
        ----------
        parent_guid:str
            GUID of parent node.
        title:str
            Title of child node.
        tags: list[sr], optional
            Tags of child node.

        Returns
        -------
        str
            GUID of newly created child node.

        Raises
        ------
        HTTPError
            Raised if POST request to OSF.io fails.
        """
        request_url = f"{self.base_url}nodes/{parent_guid}/children/"

        request_body = {
            "type": "nodes",
            "attributes": {"title": title, "category": "data", "public": True},
        }

        if tags is not None:
            request_body["attributes"]["tags"] = tags

        response = requests.post(
            request_url, headers=self.headers, json={"data": request_body}
        )
        response.raise_for_status()
        return response.json()["data"]["id"]

    def get_existing_molecules(self) -> dict[str, str]:
        """Get labels and GUIDs molecule nodes in OSF dataset.

        Returns
        -------
        dict of type str : str
            Returns dictionary of node labels mapped to node GUIDs

        Raises
        ------
        HTTPError
            Raised if GET request to OSF.io fails.
        """
        request_url = f"{self.base_url}nodes/{self.data_node_guid}/children/"
        response = requests.get(request_url, headers=self.headers)
        response.raise_for_status()
        dataset_node_children = response.json()["data"]

        existing_molecules = {
            child["attributes"]["title"]: child["id"] for child in dataset_node_children
        }

        return existing_molecules

    def post_files(self, dataset_guid: str, file_paths: list[str]):
        """Upload files to a node in OSF.io.

        Parameters
        ----------
        dataset_guid : str
            GUID of node where file is to be uploaded.
        file_paths : list[str]
            File paths of files to be uploaded.

        Returns
        -------
        bool
            True if all uploads are successful, false otherwise.
        """
        files_base_url = "http://files.ca-1.osf.io/v1/resources/"
        request_url = f"{files_base_url}{dataset_guid}/providers/osfstorage/"
        success = True

        for file_path_string in file_paths:
            file_path = Path(file_path_string)

            files = {file_path.name: open(file_path, "rb")}
            query_parameters = f"?kind=file&name={file_path.name}"
            response = requests.put(
                request_url + query_parameters, files=files, headers=self.headers
            )

            if response.status_code != 201:
                print(f"Upload {file_path} failed with code {response.status_code}")
                success = False
            else:
                print(f"Uploaded {file_path} ")

        return success