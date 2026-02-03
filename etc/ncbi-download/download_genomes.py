#!/usr/bin/env python3
"""
Download genome files (.fna.gz and .gff.gz) from NCBI for accessions in a list.
"""

import os
import sys
import re
from ftplib import FTP
from pathlib import Path
import time
import tempfile

from minio_client import MinioClient

minio_bucket = "cdm-lake"
minio_path_prefix = "tenant-general-warehouse/kbase/datasets/ncbi/"

def get_minio_client():
    """
    Initialize and return MinioClient.
    """
    client = MinioClient()

    # Ensure bucket exists
    buckets = client.list_buckets()
    if minio_bucket not in buckets:
        raise Exception(f"MinIO bucket '{minio_bucket}' does not exist.")
    
    # Ensure path prefix exists (not strictly necessary for MinIO/S3, but for sanity check)
    objects = client.list_objects(minio_bucket, prefix=minio_path_prefix)
    if not any(objects):
        raise Exception(f"MinIO path prefix '{minio_path_prefix}' does not exist in bucket '{minio_bucket}'.")

    return client



def parse_accession(entry):
    """
    Parse entry like 'GB_GCA_000195005.1' or 'RS_GCF_000006825.1'
    Returns: (prefix, database, accession_full)
    e.g., ('GB', 'GCA', 'GCA_000195005.1')
    """
    match = re.match(r'(GB|RS)_(GC[AF])_([\d.]+)', entry.strip())
    if not match:
        raise ValueError(f"Invalid entry format: {entry}")
    
    prefix = match.group(1)
    database = match.group(2)  # GCA or GCF
    accession_num = match.group(3)
    accession_full = f"{database}_{accession_num}"
    
    return prefix, database, accession_full


def build_ftp_path(database, accession_full):
    """
    Build FTP path from accession.
    e.g., GCA_000195005.1 -> /genomes/all/GCA/000/195/005/
    """
    # Extract numeric parts: GCA_000195005.1 -> ['000', '195', '005']
    match = re.match(r'GC[AF]_(\d{3})(\d{3})(\d{3})\.\d+', accession_full)
    if not match:
        raise ValueError(f"Cannot parse accession: {accession_full}")
    
    part1, part2, part3 = match.groups()
    path = f"/genomes/all/{database}/{part1}/{part2}/{part3}/"
    
    return path


def build_accession_path(assembly_dir):
    """
    Build the NCBI path for a given assembly directory.
    e.g., GCA_000195005.1_MyRecordDescription -> GCA/000/195/005/GCA_000195005.1_MyRecordDescription/
    """
    match = re.match(r'GC[AF]_(\d{3})(\d{3})(\d{3})\.\d+.*', assembly_dir)
    if not match:
        raise ValueError(f"Cannot parse accession: {assembly_dir}")
    
    part1, part2, part3 = match.groups()
    path = f"raw_data/{assembly_dir[0:3]}/{part1}/{part2}/{part3}/{assembly_dir}/"
    
    return path


def find_assembly_dir(ftp, base_path, accession_full):
    """
    Find the actual assembly directory (with assembly name suffix).
    e.g., GCA_000195005.1_ASM19500v1
    """
    try:
        ftp.cwd(base_path)
        dirs = []
        ftp.retrlines('LIST', lambda x: dirs.append(x))
        
        # Find directory that starts with our accession
        for line in dirs:
            parts = line.split()
            if len(parts) >= 9:
                name = parts[-1]
                if name.startswith(accession_full):
                    return name
        
        raise FileNotFoundError(f"No assembly directory found for {accession_full} in {base_path}")
    
    except Exception as e:
        raise Exception(f"Error finding assembly directory: {e}")


file_filters = [
    '_gene_ontology.gaf.gz',
    '_genomic.fna.gz',
    '_genomic.gff.gz',
    '_protein.faa.gz',
    '_ani_contam_ranges.tsv',
    '_assembly_regions.txt',
    '_assembly_report.txt',
    '_assembly_stats.txt',
    '_gene_expression_counts.txt.gz',
    '_normalized_gene_expression_counts.txt.gz',
]

def download_genome_files(entry, s3_client, local_dir, ftp_host='ftp.ncbi.nlm.nih.gov'):
    """
    Download files according to file_filters for a given accession.
    """
    _, database, accession_full = parse_accession(entry)
    
    # Ensure local_dir is a Path object
    local_dir = Path(local_dir)
    
    print(f"\nProcessing: {entry}")
    print(f"  Accession: {accession_full}")
    print(f"  Local temporary dir: {local_dir}")
    
    # Connect to FTP
    ftp = FTP(ftp_host)
    ftp.login()
    
    try:
        # Build path and find assembly directory
        base_path = build_ftp_path(database, accession_full)
        print(f"  Base path: {base_path}")
        
        assembly_dir = find_assembly_dir(ftp, base_path, accession_full)
        print(f"  Assembly dir: {assembly_dir}")

        s3_path = minio_path_prefix + build_accession_path(assembly_dir)
        print(f"  S3 path: {s3_path}")
        
        full_path = base_path + assembly_dir
        ftp.cwd(full_path)
        
        # List files
        files = []
        ftp.retrlines('NLST', lambda x: files.append(x))
        
        # Filter for files based on file_filters
        target_files = [f for f in files if any(f.endswith(suffix) for suffix in file_filters)]
        
        if not target_files:
            print(f"  WARNING: No files matching filters found")
            return
        
        # Download files
        for filename in target_files:
            local_file = local_dir / filename
            print(f"  Downloading: {filename}")
            
            with open(local_file, 'wb') as f:
                ftp.retrbinary(f'RETR {filename}', f.write)
            
            s3_client.upload_file(
                minio_bucket,
                s3_path + filename,
                str(local_file)
            )
            print(f"    Uploaded to MinIO: {s3_path + filename}")
        
        print(f"  ✓ Downloaded {len(target_files)} files")
    
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        raise
    
    finally:
        ftp.quit()


def main():
    if len(sys.argv) < 1:
        print("Usage: python download_genomes.py <accession_list_file>")
        print("\nExample: python download_genomes.py list_of_accessions.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    # Read accessions
    with open(input_file, 'r') as f:
        accessions = [line.strip() for line in f if line.strip()]
    
    print(f"Found {len(accessions)} accessions to process")

    # Initialize MinIO client and check bucket/path
    s3 = get_minio_client()

    # Create a temporary folder for downloads
    temp_dir = tempfile.TemporaryDirectory()
    
    # Process each accession
    success_count = 0
    failed = []
    
    for i, entry in enumerate(accessions, 1):
        try:
            print(f"\n[{i}/{len(accessions)}]", end=' ')
            download_genome_files(entry, s3, temp_dir.name)
            success_count += 1
            time.sleep(0.5)  # Be nice to NCBI servers
        
        except Exception as e:
            print(f"  ✗ FAILED: {entry}")
            failed.append((entry, str(e)))
    
    # Summary
    print("\n" + "="*60)
    print(f"SUMMARY:")
    print(f"  Total: {len(accessions)}")
    print(f"  Success: {success_count}")
    print(f"  Failed: {len(failed)}")
    
    if failed:
        print("\nFailed accessions:")
        for entry, error in failed:
            print(f"  - {entry}: {error}")


if __name__ == '__main__':
    main()
