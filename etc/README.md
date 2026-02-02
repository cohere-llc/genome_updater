# NCBI File Transfer Script

The python script in this folder downloads files from `ftp.ncbi.nlm.nih.gov`. The script
takes two arguments:
- a path to a text file containing a list of genome records to download
- a path to the local folder to store the downloaded records

Each entry in the text file is in the form:
```
{PREFIX}_{TYPE}_{ID}.{RECORD}
```
- `PREFIX`: Either `GB` (GenBank? GTDB?) or `RS` (RefSeek?). This is ignored in the query
- `DATABASE`: Either `GCA` (Seems to correspond to `GB` records?) or `GCF` (`RS` records?)
- `ID`: Nine digit ID, split into three, 3-digit parts for the query: `PART1`, `PART2`, `PART3`
- `RECORD`: Integer used to identify specific subfolders in the `ID` record. Starts at 1, goes up to the number of subfolders

The path to a specific folder's files is:
```
ftp://ftp.ncbi.nlm.nih.gov/genomes/all/{DATABASE}/{PART1}/{PART2}/{PART3}/{RECORD}_SomeLabelText
```
The text after `{RECORD}_` describes the record in some way, but only the integer record index is used in the query (this assumes one sub-folder per record id, which seems to be the case).

Here is an example list:
```
GB_GCA_000195005.1
GB_GCA_000408925.1
GB_GCA_000410835.1
GB_GCA_000452465.2
GB_GCA_000682095.1
RS_GCF_000006825.1
RS_GCF_000007865.1
RS_GCF_000008205.1
```

The local folder will be created, if it doesn't exist.

Example usage:
```
python3 download_genomes.py example_list.txt ./my-folder
```

The contents of my folder would look like this:
```
|- my-folder/
   |- GB_GCA_000195005.1/
   |- GB_GCA_000408925.1/
   |- GB_GCA_000410835.1/
   |- GB_GCA_000452465.2/
   |- GB_GCA_000682095.1/
   |- RS_GCF_000006825.1/
   |- RS_GCF_000007865.1/
   |- RS_GCF_000008205.1/
   ```