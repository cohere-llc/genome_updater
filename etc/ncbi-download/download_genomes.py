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
    path = f"{assembly_dir[0:3]}/{part1}/{part2}/{part3}/{assembly_dir}/"
    
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

def download_genome_files(entry, output_dir, ftp_host='ftp.ncbi.nlm.nih.gov'):
    """
    Download files according to file_filters for a given accession.
    """
    _, database, accession_full = parse_accession(entry)
    
    print(f"\nProcessing: {entry}")
    print(f"  Accession: {accession_full}")
    
    # Connect to FTP
    ftp = FTP(ftp_host)
    ftp.login()
    
    try:
        # Build path and find assembly directory
        base_path = build_ftp_path(database, accession_full)
        print(f"  Base path: {base_path}")
        
        assembly_dir = find_assembly_dir(ftp, base_path, accession_full)
        print(f"  Assembly dir: {assembly_dir}")

        local_dir = build_accession_path(assembly_dir)
        local_dir = Path(output_dir) / local_dir
        local_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Local dir: {local_dir}")
        
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
            
            print(f"    Saved to: {local_file}")
        
        print(f"  ✓ Downloaded {len(target_files)} files")
    
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        raise
    
    finally:
        ftp.quit()


def main():
    if len(sys.argv) < 2:
        print("Usage: python download_genomes.py <accession_list_file> [output_dir]")
        print("\nExample: python download_genomes.py list_of_accessions.txt ./genomes")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else './genomes'
    
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    # Read accessions
    with open(input_file, 'r') as f:
        accessions = [line.strip() for line in f if line.strip()]
    
    print(f"Found {len(accessions)} accessions to process")
    print(f"Output directory: {output_dir}")
    
    # Process each accession
    success_count = 0
    failed = []
    
    for i, entry in enumerate(accessions, 1):
        try:
            print(f"\n[{i}/{len(accessions)}]", end=' ')
            download_genome_files(entry, output_dir)
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
