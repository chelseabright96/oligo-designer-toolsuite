# import pybedtools

import gzip
import itertools
import logging
import os
import re
import shutil
from ftplib import FTP
from pathlib import Path

import pandas as pd
from Bio import SeqIO


class BaseFtpLoader:
    """Base class for downloading annotations from different FTP servers.

    :param dir_output: Path to directory for downloaded files.
    :type dir_output: string
    """

    def __init__(self, dir_output) -> None:
        """Constructor method"""
        self.dir_output = dir_output
        # set logger
        self.logging = logging.getLogger("probe_designer")

    def download(self, ftp_link, ftp_directory, file_name):

        """
        Download file from ftp server.
        :param ftp_link: Link to ftp server.
        :type ftp_link: string
        :param ftp_directory: Path to directory for target files.
        :type ftp_directory: string
        :param file_name: Name of target file.
        :type file_name: string
        :return: Path to downloaded file.
        :rtype: string
        """

        ftp = FTP(ftp_link)
        ftp.login()  # login to ftp server
        ftp.cwd(ftp_directory)  # move to directory

        files = ftp.nlst()

        for file in files:
            if re.match(file_name, file):
                file_output = os.path.join(self.dir_output, file)
                ftp.retrbinary("RETR " + file, open(file_output, "wb").write)

        ftp.quit()

        return file_output

    def decompress_gzip(self, file_gzip):
        """
        Decompress zip files.
        :param file_gzip: Path to zipped file.
        :type file_gzip: string
        :return: Path to unzipped file.
        :rtype: string
        """
        file_output = file_gzip.split(".gz")[0]
        with gzip.open(file_gzip, "rb") as f_in:
            with open(file_output, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(file_gzip)

        return file_output

    def download_and_decompress(self, ftp_link, ftp_directory, file_name):
        """Download genome sequence from ftp server and unzip file.

        :return: Path to downloaded file.
        :rtype: string
        """

        file_download = self.download(ftp_link, ftp_directory, file_name)
        file_unzipped = self.decompress_gzip(file_download)

        return file_unzipped

    def check_file_type(self, file_type):
        valid_file_types = ["gtf", "fasta"]

        if file_type not in valid_file_types:
            if isinstance(file_type, str):
                raise Exception(
                    f"An invalid file type name is used as input. Accepted file types: {valid_file_types}"
                )
            else:
                raise TypeError(
                    f"file_type should be a string. Accepted choices for file_type: {valid_file_types}"
                )


class FtpLoaderEnsemble(BaseFtpLoader):
    """Class for downloading annotations from Ensembl, inheriting from BaseFtpLoader.
    :param species: available species: human or mouse
    :type species: string
    :param annotation_release: release number of annotation or 'current' to use most recent annotation release. Check out release numbers for ensemble at ftp.ensembl.org/pub/
    :type annotation_release: string
    :param genome_assembly: genome assembly for species | for human: GRCh37 or GRCh38 | for mouse: GRCm38 or GRCm39
    :type genome_assembly: string
    """

    def __init__(
        self, dir_output, species, genome_assembly, annotation_release
    ) -> None:
        """Constructor method"""
        super().__init__(dir_output)
        self.species = species
        self.genome_assembly = genome_assembly
        self.annotation_release = annotation_release

    def get_params(self, file_type):
        """Get directory and file name for gtf and fasta files from Ensembl server
        :param dir_output: Path to directory for downloaded files.
        :type dir_output: string
        :return: ftp directories and file names of gtf and fasta files from Ensembl server.
        :rtype: tuple of strings
        """

        self.check_file_type(file_type)

        Path(self.dir_output).mkdir(parents=True, exist_ok=True)

        self.ftp_link = self.generate_FTP_link()

        if self.species == "human":
            species_id = "homo_sapiens"
        if self.species == "mouse":
            species_id = "mus_musculus"

        if self.annotation_release == "current":
            file_readme = self.download(self.ftp_link, "pub/", "current_README")
            with open(file_readme, "r") as handle:
                for line in handle:
                    if line.startswith("Ensembl Release"):
                        annotation_release = line.strip().split(" ")[2]
            os.remove(file_readme)

        if file_type.casefold() == "gtf".casefold():

            ftp_directory = f"pub/release-{annotation_release}/gtf/{species_id}/"
            ftp_file = f"{species_id.capitalize()}.{self.genome_assembly}.{annotation_release}.gtf"

        elif file_type.casefold() == "fasta".casefold():

            ftp_directory = f"pub/release-{annotation_release}/fasta/{species_id}/dna/"
            ftp_file = f"{species_id.capitalize()}.{self.genome_assembly}.dna_rm.primary_assembly.fa"

        return ftp_directory, ftp_file

    def generate_FTP_link(self):
        return "ftp.ensembl.org"

    def download_files(self, file_type):
        """Download gene annotation in file_type format from ensembl and unzip file.

        :return: Path to downloaded file.
        :rtype: string
        """
        ftp_directory, ftp_file = self.get_params(file_type)
        output_file = self.download_and_decompress(
            self.ftp_link, ftp_directory, ftp_file
        )

        return output_file


class FTPLoaderNCBI(BaseFtpLoader):
    """Class for downloading annotations from NCBI, inheriting from BaseFtpLoader.
    :param species: available species: human or mouse
    :type species: string
    :param annotation_release: release number (e.g. 109 or 109.20211119) of annotation or 'current' to use most recent annotation release. Check out release numbers for NCBI at ftp.ncbi.nlm.nih.gov/refseq/H_sapiens/annotation/annotation_releases/.
    :type annotation_release: string
    :param genome_assembly: genome assembly for species | for human: GRCh37 or GRCh38 | for mouse: GRCm38 or GRCm39
    :type genome_assembly: string
    """

    def __init__(
        self, dir_output, species, genome_assembly, annotation_release
    ) -> None:
        """Constructor method"""
        super().__init__(dir_output)
        self.species = species
        self.genome_assembly = genome_assembly
        self.annotation_release = annotation_release

        self.ftp_link = self.generate_FTP_link()

    def get_params(self, file_type):
        """Get directory and file name for specified file type from NCBI server
        :param file_type: File type to download (e.g. gtf or fasta)
        :type file_type: string
        :return: ftp directories and file names of specified file type from NCBI server.
        :rtype: tuple of strings
        """

        self.check_file_type(file_type)

        Path(self.dir_output).mkdir(parents=True, exist_ok=True)

        if self.species == "human":
            ftp_directory = "refseq/H_sapiens/annotation/annotation_releases/"
        if self.species == "mouse":
            ftp_directory = "refseq/M_musculus/annotation_releases/"

        if self.annotation_release == "current":
            ftp_directory = ftp_directory + "current/"
        else:
            ftp_directory = ftp_directory + f"{self.annotation_release}/"

        file_readme = self.download(self.ftp_link, ftp_directory, "README")
        with open(file_readme, "r") as handle:
            for line in handle:
                if line.startswith("ASSEMBLY NAME:"):
                    assembly_name = line.strip().split("\t")[1]
                if line.startswith("ASSEMBLY ACCESSION:"):
                    assembly_accession = line.strip().split("\t")[1]
                    break
        os.remove(file_readme)

        ftp_directory = ftp_directory + f"{assembly_accession}_{assembly_name}"

        if file_type.casefold() == "gtf".casefold():
            ftp_file = f"{assembly_accession}_{assembly_name}_genomic.gtf.gz"

        elif file_type.casefold() == "fasta".casefold():
            ftp_file = f"{assembly_accession}_{assembly_name}_genomic.fna.gz"

        ftp_file_chr_mapping = (
            f"{assembly_accession}_{assembly_name}_assembly_report.txt"
        )

        return ftp_directory, ftp_file, ftp_file_chr_mapping

    def generate_FTP_link(self):
        return "ftp.ncbi.nlm.nih.gov"

    def _download_mapping_chr_names(self, ftp_directory, ftp_file_chr_mapping):
        """Download file with mapping of chromosome names between GenBank and Ref-Seq accession number
        from ftp server and create a mapping dictionary.

        :param ftp_file_chr_mapping: Name of file that should be downloaded from ftp server
        :type ftp_file_chr_mapping: string
        :return: Dictionary with mapping of chromsome names from GenBank to Ref-Seq.
        :rtype: dict
        """

        file_mapping = self.download(self.ftp_link, ftp_directory, ftp_file_chr_mapping)

        # skip comment lines but keep last comment line for header
        with open(file_mapping) as handle:
            *_comments, names = itertools.takewhile(
                lambda line: line.startswith("#"), handle
            )
            names = names[1:].split()

        assembly_report = pd.read_table(
            file_mapping, names=names, sep="\t", comment="#"
        )

        mapping_chromosome = assembly_report[
            assembly_report["Sequence-Role"] == "assembled-molecule"
        ]
        mapping_chromosome = pd.Series(
            mapping_chromosome["Sequence-Name"].values,
            index=mapping_chromosome["RefSeq-Accn"],
        ).to_dict()

        mapping_scaffolds = assembly_report[
            assembly_report["Sequence-Role"] != "assembled-molecule"
        ]
        mapping_scaffolds = pd.Series(
            mapping_scaffolds["GenBank-Accn"].values,
            index=mapping_scaffolds["RefSeq-Accn"],
        ).to_dict()

        mapping = mapping_chromosome
        mapping.update(mapping_scaffolds)

        return mapping

    def _map_chr_names_gene_gtf(self, ftp_file, mapping):

        """Process gene annotation file downloaded from NCBI: map chromosome annotation to Ref-Seq.
        :param file_gene_gtf: Path to gtf file with gene annotation.
        :type file_gene_gtf: string
        :param mapping: Chromosome mapping dictionary (GenBank to Ref-Seq).
        :type mapping: dict
        """
        file_tmp = os.path.join(self.dir_output, "temp.gtf")

        # write comment lines to new file
        with open(file_tmp, "w") as handle_out:
            with open(ftp_file) as handle_in:
                *_comments, names = itertools.takewhile(
                    lambda line: line.startswith("#"), handle_in
                )
                handle_out.write(names)

            # read gtf file without comment lines
            gene_annotation = pd.read_table(
                ftp_file,
                names=[
                    "seqname",
                    "source",
                    "feature",
                    "start",
                    "end",
                    "score",
                    "strand",
                    "frame",
                    "attribute",
                ],
                sep="\t",
                comment="#",
            )

            # replace ncbi with genbank chromosome annotation
            gene_annotation["seqname"] = gene_annotation["seqname"].map(mapping)
            gene_annotation.dropna(inplace=True)  # drop if no mapping exists

            gene_annotation.to_csv(handle_out, sep="\t", header=False, index=False)
        os.replace(file_tmp, ftp_file)

    def _map_chr_names_genome_fasta(self, ftp_file, mapping):

        """Process genome sequence file downloaded from NCBI: map chromosome annotation to Ref-Seq.
        :param file_genome_fasta: Path to fasta file with genome sequence.
        :type file_genome_fasta: string
        :param mapping: Chromosome mapping dictionary (GenBank to Ref-Seq).
        :type mapping: dict
        """

        file_tmp = os.path.join(self.dir_output, "temp.fna")

        with open(file_tmp, "w") as handle:
            for chromosome_sequnece in SeqIO.parse(ftp_file, "fasta"):
                accession_number = chromosome_sequnece.id
                if accession_number in mapping:
                    chromosome_sequnece.id = mapping[accession_number]
                    chromosome_sequnece.name = mapping[accession_number]
                    chromosome_sequnece.description = (
                        chromosome_sequnece.description.replace(
                            accession_number, mapping[accession_number]
                        )
                    )
                    SeqIO.write(chromosome_sequnece, handle, "fasta")
                else:
                    self.logging.info(
                        "No mapping for accession number: {}".format(accession_number)
                    )

        os.replace(file_tmp, ftp_file)

    def download_files(self, file_type, mapping=None):
        """Download gene annotation in file_type format from NCBI and unzip file.
        Map chromosome annotation to Ref-Seq accession number.
        :param mapping: Chromosome mapping dictionary (GenBank to Ref-Seq).
        :type mapping: dict
        :return: Path to downloaded file.
        :rtype: string
        """

        ftp_directory, ftp_file, ftp_file_chr_mapping = self.get_params(file_type)
        mapping = self._download_mapping_chr_names(ftp_directory, ftp_file_chr_mapping)
        output_file = self.download_and_decompress(
            self.ftp_link, ftp_directory, ftp_file
        )

        if file_type.casefold() == "gtf".casefold():
            self._map_chr_names_gene_gtf(output_file, mapping)

        elif file_type.casefold() == "gtf".casefold():
            self._map_chr_names_genome_fasta(output_file, mapping)

        return output_file
