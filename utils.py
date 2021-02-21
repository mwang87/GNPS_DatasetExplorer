
import pandas as pd
import requests
import os
import metabolights


def get_dataset_files(accession, metadata_source, dataset_password="", metadata_option=None):
    """This gives a pandas dataframe with files and appended metadata

    Args:
        accession ([type]): [description]
        metadata_source ([type]): [description]

    Returns:
        [type]: [description]
    """

    file_df = pd.DataFrame()

    if "MSV" in accession:
        files_df = _get_massive_files(accession, dataset_password=dataset_password)

        if metadata_source == "REDU":
            files_df = _add_redu_metadata(files_df, accession)
        elif metadata_source == "MASSIVE":
            files_df = _add_massive_metadata(files_df, accession, metadata_option=metadata_option)

    elif "MTBLS" in accession:
        all_files = _get_mtbls_files(accession)
        temp_df = pd.DataFrame(all_files)
        files_df = pd.DataFrame()
        files_df["filename"] = temp_df["file"]
        files_df = metabolights.add_mtbls_metadata(files_df, accession)

    elif "PXD" in accession:
        all_files = _get_pxd_files(accession)
        files_df = pd.DataFrame(all_files)

    elif "ST" in accession:
        files_df, dataset_accession = _get_metabolomicsworkbench_files(accession)

    elif "JGI:" in accession:
        all_files = _get_jgi_files(accession)
        temp_df = pd.DataFrame(all_files)
        files_df = pd.DataFrame()
        files_df["filename"] = temp_df["filename"]

    elif len(accession) == 32:
        # We're likely looking at a uuid from GNPS, lets hit the API
        all_files = _get_gnps_task_files(accession)
        files_df = pd.DataFrame(all_files)
        files_df = _add_task_metadata(files_df, accession)

    return files_df   

def get_dataset_description(accession):
    """Getting title and description of a dataset

    Args:
        accession ([type]): [description]

    Returns:
        [type]: [description]
    """

    dataset_title = "Dataset Title - Error"
    dataset_description = "Error Description"

    if "MSV" in accession:
        dataset_title, dataset_description = _get_massive_dataset_information(accession)

    if "MTBLS" in accession:
        dataset_title, dataset_description = _get_mtbls_dataset_information(accession)

    if "PXD" in accession:
        dataset_title, dataset_description = _get_pxd_dataset_information(accession)
    
    if "ST" in accession:
        dataset_title, dataset_description = _get_metabolomicsworkbench_dataset_information(accession)

    elif len(accession) == 32:
        # We're likely looking at a uuid from GNPS, lets hit the API
        dataset_title, dataset_description = _get_gnps_task_information(accession)

    return  dataset_title, dataset_description


def _get_gnps_task_files(gnps_task):
    url = "https://gnps.ucsd.edu/ProteoSAFe/ManageParameters?task={}".format(gnps_task)
    r = requests.get(url)
    import xmltodict
    r_json = xmltodict.parse(r.text)

    all_files = []
    for parameter in r_json["parameters"]["parameter"]:
        if parameter["@name"] == "upload_file_mapping":
            filename = parameter["#text"].split("|")[1]
            all_files.append(filename)

    acceptable_extensions = [".mzml", ".mzxml", ".cdf", ".raw", ".mgf"]

    all_files = [filename for filename in all_files if os.path.splitext(filename)[1].lower() in acceptable_extensions]

    output_list = []
    for filename in all_files:
        output_dict = {}
        output_dict["filename"] = filename
        output_list.append(output_dict)

    return output_list

def _get_gnps_task_information(accession):
    url = "https://gnps.ucsd.edu/ProteoSAFe/status_json.jsp?task={}".format(accession)
    r = requests.get(url)
    task_information = r.json()

    return task_information["description"], "ProteoSAFe Task {} - Workflow {} - Version {} - User {}".format(accession, task_information["workflow"], task_information["workflow_version"], task_information["user"])

def _get_massive_files(dataset_accession, dataset_password=""):
    all_files_df = pd.DataFrame()

    try:
        all_files_df = _get_massive_files_cached(dataset_accession)
    except:
        pass

    if len(all_files_df) == 0:
        all_files_df = _get_massive_files_ftp(dataset_accession, dataset_password=dataset_password)
        
    all_files_df["filepath"] = all_files_df["filepath"].apply(lambda x: x.replace(dataset_accession + "/", "") )
    
    files_df = pd.DataFrame()
    files_df["filename"] = all_files_df["filepath"]

    # Adding more information if possible
    if "collection" in all_files_df:
        files_df["collection"] = all_files_df["collection"]
        files_df["update_name"] = all_files_df["update_name"]

    if "size_mb" in all_files_df:
        files_df["size_mb"] = all_files_df["size_mb"]
        files_df["ms2"] = all_files_df["spectra_ms2"]
        files_df["Vendor"] = all_files_df["instrument_vendor"]
        files_df["Model"] = all_files_df["instrument_model"]

    return files_df


def _get_massive_files_ftp(dataset_accession, dataset_password=""):
    import ftputil
    import ming_proteosafe_library

    if len(dataset_password) > 0:
        massive_host = ftputil.FTPHost("massive.ucsd.edu", dataset_accession, dataset_password)
    else:
        massive_host = ftputil.FTPHost("massive.ucsd.edu", "anonymous", "")

    all_files = ming_proteosafe_library.get_all_files_in_dataset_folder_ftp(dataset_accession, "ccms_peak", massive_host=massive_host, dataset_password=dataset_password)
    all_files += ming_proteosafe_library.get_all_files_in_dataset_folder_ftp(dataset_accession, "peak", massive_host=massive_host, dataset_password=dataset_password)
    all_files += ming_proteosafe_library.get_all_files_in_dataset_folder_ftp(dataset_accession, "raw", massive_host=massive_host, dataset_password=dataset_password)

    acceptable_extensions = [".mzml", ".mzxml", ".cdf", ".raw"]

    all_files = [filename for filename in all_files if os.path.splitext(filename)[1].lower() in acceptable_extensions]

    all_files_df = pd.DataFrame()
    all_files_df["filepath"] = all_files

    return all_files_df

def _get_massive_files_cached(dataset_accession):
    url = "http://dorresteintesthub.ucsd.edu:5235/datasette/database/filename.csv?_stream=on&_sort=filepath&dataset__exact={}&_size=max".format(dataset_accession)
    #url = "http://mingwangbeta.ucsd.edu:5235/datasette/database/filename.csv?_stream=on&_sort=filepath&dataset__exact={}&_size=max".format(dataset_accession)
    all_files_df = pd.read_csv(url, sep=",")

    all_files = list(all_files_df["filepath"])

    acceptable_extensions = [".mzml", ".mzxml", ".cdf", ".raw"]
    
    all_files = [filename for filename in all_files if os.path.splitext(filename)[1].lower() in acceptable_extensions]

    all_files_df = all_files_df[all_files_df["filepath"].isin(all_files)]

    return all_files_df

def _get_massive_dataset_information(dataset_accession):
    url = "http://massive.ucsd.edu/ProteoSAFe/proxi/v0.1/datasets/{}".format(dataset_accession)
    r = requests.get(url)
    dataset_information = r.json()

    return dataset_information["title"], dataset_information["summary"]

def _get_mtbls_files(dataset_accession):
    url = "https://www.ebi.ac.uk:443/metabolights/ws/studies/{}/files/tree?include_sub_dir=true".format(dataset_accession)
    r = requests.get(url)

    acceptable_types = ['raw', 'derived']
    
    all_files = r.json()["study"]
    all_files = [file_obj for file_obj in all_files if file_obj["directory"] is False]
    all_files = [file_obj for file_obj in all_files if file_obj["type"] in acceptable_types]

    acceptable_extensions = [".mzml", ".mzxml", ".cdf", ".raw"]

    acceptable_files = []
    for file_object in all_files:
        try:
            if os.path.splitext(file_object["file"])[1].lower() in acceptable_extensions:
                acceptable_files.append(file_object)
        except:
            pass
    
    return acceptable_files

def _get_mtbls_dataset_information(dataset_accession):
    url = "https://www.ebi.ac.uk/metabolights/ws/studies/{}/description".format(dataset_accession)
    r = requests.get(url)
    description = r.json()["description"]

    url = "https://www.ebi.ac.uk/metabolights/ws/studies/{}/title".format(dataset_accession)
    r = requests.get(url)
    title = r.json()["title"]
     
    return title, description


def _get_metabolomicsworkbench_files(dataset_accession):
    # Lets see if it is in massive
    massive_datasets = requests.get("https://massive.ucsd.edu/ProteoSAFe/datasets_json.jsp").json()["datasets"]

    massive_datasets = [dataset for dataset in massive_datasets if dataset_accession in dataset["title"]]

    if len(massive_datasets) == 0:
        return pd.DataFrame(), ""
    
    dataset_accession = massive_datasets[0]["dataset"]

    return _get_massive_files(dataset_accession), dataset_accession
        
def _get_metabolomicsworkbench_dataset_information(dataset_accession):
    metabolomics_workbench_data = requests.get("https://www.metabolomicsworkbench.org/rest/study/study_id/{}/summary".format(dataset_accession)).json()

    return metabolomics_workbench_data["study_title"], metabolomics_workbench_data["study_summary"]


def _get_jgi_files(dataset_accession):
    url = "https://genome.jgi.doe.gov/portal/ext-api/downloads/get-directory?organism={}&organizedByFileType=false".format(dataset_accession.replace("JGI:", ""))
    session = requests.Session()
    r = session.post('https://signon.jgi.doe.gov/signon/create', params={"login": "", "password": ''})
    cookies = session.cookies.get_dict()

    r = session.get(url, cookies=cookies)

    acceptable_extensions = [".raw", ".mzML", ".mzXML", ".CDF", ".RAW", "cdf"]

    output_list = []

    import xmltodict as xtd
    import json
    dataset_list = xtd.parse(r.text)
    all_folders = dataset_list["organismDownloads"]["folder"]["folder"][0]["folder"][0]["folder"]

    for folder in all_folders:
        file_url = "https://genome.jgi.doe.gov{}".format(folder["file"]["@url"])
        filename = folder["file"]["@filename"]

        _, extension = os.path.splitext(filename)

        if extension in acceptable_extensions:
            output_dict = {}
            output_dict["filename"] = filename
            output_dict["remote_link"] = file_url
            output_list.append(output_dict)

    return output_list 


def _get_pxd_files(dataset_accession):
    url = "http://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={}&outputMode=json&test=no".format(dataset_accession)
    r = requests.get(url)
    
    acceptable_extensions = [".raw", ".mzML", ".mzXML", ".CDF", ".RAW", "cdf"]

    all_files = r.json()["datasetFiles"]
    output_list = []
    for file_object in all_files:
        remote_path = file_object["value"]
        filename, extension = os.path.splitext(remote_path)
        if extension in acceptable_extensions:
            output_dict = {}
            output_dict["filename"] = os.path.basename(remote_path)
            output_list.append(output_dict)
    
    return output_list

def _get_pxd_dataset_information(dataset_accession):
    url = "http://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={}&outputMode=json&test=no".format(dataset_accession)
    r = requests.get(url)

    title = r.json()["title"]
    description = r.json()["description"]
     
    return title, description

def _add_redu_metadata(files_df, accession):
    redu_metadata = pd.read_csv("https://redu.ucsd.edu/dump", sep='\t')
    files_df["filename"] = "f." + accession + "/" + files_df["filename"]
    files_df = files_df.merge(redu_metadata, how="left", on="filename")
    files_df = files_df[["filename", "MassSpectrometer", "SampleType", "SampleTypeSub1"]]
    files_df["filename"] = files_df["filename"].apply(lambda x: x.replace("f.{}/".format(accession), ""))

    return files_df


def _get_massive_metadata_options(accession):
    dataset_information = requests.get("https://massive.ucsd.edu/ProteoSAFe/MassiveServlet?function=massiveinformation&massiveid={}&_=1601057558273".format(accession)).json()
    dataset_task = dataset_information["task"]

    url = "https://massive.ucsd.edu/ProteoSAFe/result_json.jsp?task={}&view=view_metadata_list".format(dataset_task)
    metadata_list = requests.get("https://massive.ucsd.edu/ProteoSAFe/result_json.jsp?task={}&view=view_metadata_list".format(dataset_task)).json()["blockData"]

    return metadata_list

def _add_massive_metadata(files_df, accession, metadata_option=None):
    try:
        # Getting massive task from accession
        metadata_list = _get_massive_metadata_options(accession)

        if len(metadata_list) == 0:
            return files_df
        
        if metadata_option is not None and len(metadata_option) > 0:
            metadata_filename = [metadata_file["File_descriptor"] for metadata_file in metadata_list if metadata_file["File_descriptor"] == metadata_option][0]
        else:
            metadata_filename = metadata_list[0]["File_descriptor"]

        ftp_url = "ftp://massive.ucsd.edu/{}".format(metadata_filename.replace("f.", ""))

        metadata_df = pd.read_csv(ftp_url, sep=None)

        files_df["fullfilename"] = files_df["filename"]
        files_df["filename"] = files_df["filename"].apply(lambda x: os.path.basename(x))
        files_df = files_df.merge(metadata_df, how="left", on="filename")

        files_df["filename"] = files_df["fullfilename"]
        files_df = files_df.drop("fullfilename", axis=1)
    except:
        pass

    return files_df

def _add_task_metadata(files_df, task):
    try:
        # Trying to get classical network metadata
        url = "https://gnps.ucsd.edu/ProteoSAFe/result_json.jsp?task={}&view=view_metadata".format(task)
        metadata_df = pd.DataFrame(requests.get(url).json()["blockData"])

        files_df["fullfilename"] = files_df["filename"]
        files_df["filename"] = files_df["fullfilename"].apply(lambda x: os.path.basename(x))
        
        metadata_df["filename"] = metadata_df["_dyn_#filename"].apply(lambda x: x.replace("_dyn_#", ""))
        files_df = files_df.merge(metadata_df, how="left", on="filename")

        files_df = files_df.drop("fullfilename", axis=1)
        files_df = files_df.drop("_dyn_#filename", axis=1)
    except:
        pass

    return files_df