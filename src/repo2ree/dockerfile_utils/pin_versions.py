
from enum import Enum
import shlex
import datetime
import tempfile

from dockerfile_parse import DockerfileParser
from pydantic import BaseModel, model_validator

from repo2ree.debian_packages_util.pin_package import (
    get_latest_apt_package_version_until_date as pin_apt_package_version, 
    get_put_snapshot_sources_shell_command,
    )
from repo2ree.dockerfile_utils.os_utils import OSReleaseInfo, get_os_release_lightweight, parse_os_release, get_docker_image_digest
from repo2ree.python_packages_util.pin_pypi_package_version import get_latest_version_on_pypi_until_date

###################
# Constants
###################

SHELL_COMMAND_DELIMITERS = ["&&", ";", "||"]
SHELL_REDIRECT_OPERATORS = [">", ">>", "<", "<<", "2>", "2>>", "&>", "&>>"]

###################
# Data Models
###################

class DockerfileInstruction(BaseModel, frozen=True):

    instruction: str
    start_line: int
    end_line: int
    content: str
    value: str

class SplittedShellCommand(BaseModel, frozen=True):

    """
    Example:

    {
    "shell_command": "apt-get update && apt-get install -y curl gnupg2 ca-certificates lsb-release",
    "delimited_commands": [
        "apt-get update",
        "apt-get install -y curl gnupg2 ca-certificates lsb-release"
    ],
    "delimiters": [
        "&&"
    ],
    "delimited_commands_tokens": [
        [
        "apt-get",
        "update"
        ],
        [
        "apt-get",
        "install",
        "-y",
        "curl",
        "gnupg2",
        "ca-certificates",
        "lsb-release"
        ]
    ]
    }
    """

    shell_command: str
    delimited_commands: list[str]
    delimiters: list[str]
    delimited_commands_tokens: list[list[str]]

    @model_validator(mode="after")
    def validate_split(self) -> "SplittedShellCommand":

        if len(self.delimited_commands) != len(self.delimited_commands_tokens):
            raise ValueError("Length of delimited_commands and delimited_commands_tokens must be the same.")
        
        if len(self.delimited_commands) - 1 != len(self.delimiters):
            raise ValueError("Length of delimiters must be one less than length of delimited_commands.")
        
        rejoined_shell_command = ""
        for i, command in enumerate(self.delimited_commands):
            if i > 0:
                rejoined_shell_command += f" {self.delimiters[i - 1]} "
            rejoined_shell_command += command

        if shlex.split(rejoined_shell_command) != shlex.split(self.shell_command):
            print(shlex.split(rejoined_shell_command))
            print(shlex.split(self.shell_command))
            raise ValueError("Reconstructed command does not match the original shell_command.")
        
        for i in range(len(self.delimited_commands)):
            rejoined_delimited_command = ' '.join(self.delimited_commands_tokens[i])
            if shlex.split(rejoined_delimited_command) != shlex.split(self.delimited_commands[i]):
                raise ValueError(f"Reconstructed delimited command at index {i} does not match the original delimited command.")

        return self

class PackageInstallCommand(Enum):
    APT = "apt-get install"
    PIP = "pip install"
    NONE = "none"

class PackageManager(Enum):
    APT = "apt"
    PIP = "pip"

###################
# Main Functions
###################

def pin_dockerfile_base_image_and_packages(
        dockerfile_contents: str, 
        date: datetime.datetime,
        ) -> str:

    with tempfile.TemporaryDirectory() as tmpdir:

        dfp = DockerfileParser(tmpdir)

        dfp.content = dockerfile_contents

        #original_from = dfp.baseimage

        print(dfp.parent_images)
        print(dfp.baseimage)
        
        pinned_base_image = pin_base_image(image_name=dfp.baseimage, date=date)
        dfp.baseimage = pinned_base_image

        architecture, os_release_str = get_os_release_lightweight(image_name=dfp.baseimage)
        print(f"Architecture: {architecture}")
        print(f"/etc/os-release:\n{os_release_str}")
        os_release_info = parse_os_release(os_release_str)

        snapshot_sources_command = get_put_snapshot_sources_shell_command(
            snapshot_date=date, 
            version_code=os_release_info.version_code_name, 
            os_release_id=os_release_info.id, 
            debian_backports=True,
            keep_apt_cache=True,
        )

        dockerfile_instructions = []
        for instruction_dict in dfp.structure:
            dockerfile_instruction = DockerfileInstruction(
                instruction=instruction_dict['instruction'],
                start_line=instruction_dict['startline'],
                end_line=instruction_dict['endline'],
                content=instruction_dict['content'],
                value=instruction_dict['value'],
            )
            dockerfile_instructions.append(dockerfile_instruction)

        new_dockerfile_instructions = pin_dockerfile_package_install_commands(
            dockerfile_instructions=dockerfile_instructions,
            date=date,
            os_release_info=os_release_info,
            architecture=architecture,
            snapshot_sources_command=snapshot_sources_command,
        )

        final_content = ""
        for new_dockerfile_instruction in new_dockerfile_instructions:
            if new_dockerfile_instruction.instruction == "COMMENT":
                final_content += f"# {new_dockerfile_instruction.value}\n"
            else:
                final_content += f"{new_dockerfile_instruction.instruction} {new_dockerfile_instruction.value}\n\n"

        dfp.content = final_content

        print("-----")
        print(dfp.structure)
        print("-----")

        pinned_dockerfile_contents = final_content

    return pinned_dockerfile_contents

###################
# Impure Functions
###################

def pin_base_image(image_name: str, date: datetime.date) -> str:

    #TODO pin by specified date

    new_image_name = ""

    image_digest = get_docker_image_digest(image_name=image_name)
    if image_digest:
        base_image_repo_url = image_name.split(":")[0]
        pinned_image = base_image_repo_url + "@" + image_digest.split("@")[1]
        print(f"Pinned base image '{image_name}' to its digest '{pinned_image}'")
        new_image_name = pinned_image
    else:
        print(f"Could not pin base image '{image_name}'. Using original.")
        new_image_name = image_name
    
    return new_image_name


def pin_dockerfile_package_install_commands(
        dockerfile_instructions: list[DockerfileInstruction], 
        date: datetime.datetime,
        os_release_info: OSReleaseInfo,
        architecture: str,
        snapshot_sources_command: str,
        ) -> list[DockerfileInstruction]:

    new_dockerfile_instructions = []

    for dockerfile_instruction in dockerfile_instructions:

        new_dockerfile_instruction = DockerfileInstruction(
                    instruction=dockerfile_instruction.instruction,
                    start_line=dockerfile_instruction.start_line,
                    end_line=dockerfile_instruction.end_line,
                    content=dockerfile_instruction.content,
                    value=dockerfile_instruction.value,
                )

        if dockerfile_instruction.instruction == "RUN":

            splitted_shell_command = split_shell_command(dockerfile_instruction.value)
            print(splitted_shell_command)
            #Path("debug.json").write_text(splitted_shell_command.model_dump_json(indent=2))

            new_delimited_commands = []
            for i, _ in enumerate(splitted_shell_command.delimited_commands):
                new_delimited_command_tokens = pin_package_versions_of_install_command(
                    command_tokens=splitted_shell_command.delimited_commands_tokens[i],
                    date=date,
                    os_release_info=os_release_info,
                    architecture=architecture,
                )
                new_delimited_commands.append(' '.join(new_delimited_command_tokens))
            
            new_shell_command = ""
            for i, new_command in enumerate(new_delimited_commands):
                if i > 0:
                    new_shell_command += f" {splitted_shell_command.delimiters[i - 1]} "
                new_shell_command += new_command

            if new_shell_command != splitted_shell_command.shell_command:
                print(f"Updated shell command:\nFrom: {splitted_shell_command.shell_command}\nTo:   {new_shell_command}")

                new_dockerfile_instruction = DockerfileInstruction(
                    instruction=dockerfile_instruction.instruction,
                    start_line=dockerfile_instruction.start_line,
                    end_line=dockerfile_instruction.end_line,
                    content=f"RUN {new_shell_command}",
                    value=new_shell_command,
                )
            else:
                print(f"No changes made to shell command: {splitted_shell_command.shell_command}")
        
        new_dockerfile_instructions.append(new_dockerfile_instruction)

        if dockerfile_instruction.instruction == "FROM":
            new_dockerfile_instructions.append(DockerfileInstruction(
                instruction="RUN",
                start_line=-1,
                end_line=-1,
                content=f"RUN {snapshot_sources_command.strip()}",
                value=snapshot_sources_command.strip(),
            ))
            print(f"Inserted snapshot sources command after FROM: {snapshot_sources_command.strip()}")
    
    return new_dockerfile_instructions

    
def pin_package_versions_of_install_command(
        command_tokens: list[str],
        date: datetime.datetime,
        os_release_info: OSReleaseInfo,
        architecture: str,
        ) -> list[str]:

    install_command = parse_install_command(command_tokens)
    pinned_packages_install_command_tokens = []

    if install_command == PackageInstallCommand.NONE:
        pinned_packages_install_command_tokens = command_tokens
    else:
        packages = extract_packages_from_install_command(command_tokens, install_command)
        print(f"Extracted packages: {packages}")
        
        pinned_packages = {}
        for package in packages:
            print(package)
            if package_is_pinned(package, install_command):
                print(f"Package '{package}' is already pinned. Skipping.")
                continue
            version = lookup_package_version(
                package_name=package,
                date=date,
                os_release_info=os_release_info,
                architecture=architecture,
                install_command=install_command,
            )
            print(f"Pinned package '{package}' to version '{version}'")
            pinned_packages[package] = version

        pinned_packages_install_command_tokens = put_pinned_versions_into_install_command(command_tokens, pinned_packages, install_command)        
        
    return pinned_packages_install_command_tokens

            
def lookup_package_version(package_name: str, date: datetime.datetime, os_release_info: OSReleaseInfo, architecture: str, install_command: PackageInstallCommand) -> str:

    version = ""

    match install_command:
        case PackageInstallCommand.APT:
            version = pin_apt_package_version(
                package_name=package_name,
                date=date,
                os_release_info=os_release_info,
                architecture=architecture,
                )
        case PackageInstallCommand.PIP:
            version = get_latest_version_on_pypi_until_date(package_name, date)
            if not version:
                raise ValueError(f"Could not find a PyPI version for package '{package_name}' until date {date.isoformat()}")
        case _:
            raise ValueError(f"Unsupported package install command: {install_command}")
    
    return version


###################
# Pure Functions
###################

def split_shell_command(command: str) -> SplittedShellCommand:

    original_command = command

    tokens = shlex.split(command)
    
    delimited_command = []
    delimited_command_tokens = []
    delimiters = []
    delimited_command_tokens_buffer = []

    for token in tokens:
        if " " in token:
            token = shlex.quote(token)
        if token in SHELL_COMMAND_DELIMITERS:
            delimiters.append(token)
            delimited_command.append(' '.join(delimited_command_tokens_buffer))
            delimited_command_tokens.append(delimited_command_tokens_buffer)
            delimited_command_tokens_buffer = []
        else:
            delimited_command_tokens_buffer.append(token)
    
    delimited_command.append(' '.join(delimited_command_tokens_buffer))
    delimited_command_tokens.append(delimited_command_tokens_buffer)
    delimited_command_tokens_buffer = []

    splitted_shell_command = SplittedShellCommand(
        shell_command=original_command,
        delimited_commands=delimited_command,
        delimiters=delimiters,
        delimited_commands_tokens=delimited_command_tokens,
    )

    return splitted_shell_command


def parse_install_command(command_tokens: list[str]) -> PackageInstallCommand:

    package_install_command: PackageInstallCommand

    if "apt-get" in command_tokens and "install" in command_tokens:
        package_install_command = PackageInstallCommand.APT
    elif "pip" in command_tokens and "install" in command_tokens:
        package_install_command = PackageInstallCommand.PIP
    else:
        package_install_command = PackageInstallCommand.NONE
    
    return package_install_command


def extract_packages_from_install_command(command_tokens: list[str], install_command: PackageInstallCommand) -> list[str]:

    packages = []
    
    match install_command:
        case PackageInstallCommand.APT:
            if "apt-get" in command_tokens and "install" in command_tokens:
                install_index = command_tokens.index("install")
        
        case PackageInstallCommand.PIP:
            if "pip" in command_tokens and "install" in command_tokens:
                install_index = command_tokens.index("install")
        
        case _:
            raise ValueError(f"Unsupported package install command: {install_command}")
        
    for token in command_tokens[install_index + 1:]:
        if token in SHELL_REDIRECT_OPERATORS:
            break
        if token.startswith("-"):
            continue
        packages.append(token)

    return packages


def package_is_pinned(package_name: str, package_install_command: PackageInstallCommand) -> bool:

    is_pinned = False

    match package_install_command:
        case PackageInstallCommand.APT:
            if "=" in package_name:
                is_pinned = True
        case PackageInstallCommand.PIP:
            if "==" in package_name or ">=" in package_name or "<=" in package_name or ">" in package_name or "<" in package_name or "~=" in package_name:
                is_pinned = True
        case _:
            raise ValueError(f"Unsupported package install command: {package_install_command}")
    
    return is_pinned


def put_pinned_versions_into_install_command(command_tokens: list[str], pinned_versions: dict[str, str], install_command: PackageInstallCommand) -> list[str]:

    new_command_tokens = []

    match install_command:
        case PackageInstallCommand.APT:
    
            if "apt-get" in command_tokens and "install" in command_tokens:
                install_index = command_tokens.index("install")
        
        case PackageInstallCommand.PIP:
            if "pip" in command_tokens and "install" in command_tokens:
                install_index = command_tokens.index("install")

        case _:
            raise ValueError(f"Unsupported package install command: {install_command}")
    
    new_command_tokens = command_tokens[:install_index + 1]
    for token in command_tokens[install_index + 1:]:
        if token in SHELL_REDIRECT_OPERATORS:
            new_command_tokens.append(token)
            continue
        if token.startswith("-"):
            new_command_tokens.append(token)
            continue
        if token in pinned_versions:
            pinned_version = put_pinned_package_version(token, pinned_versions[token], install_command)
            new_command_tokens.append(pinned_version)
        else:
            new_command_tokens.append(token)

    return new_command_tokens


def put_pinned_package_version(package_name: str, version: str, install_command: PackageInstallCommand) -> str:

    pinned_package = ""

    match install_command:
        case PackageInstallCommand.APT:
            pinned_package = f"{package_name}={version}"
        case PackageInstallCommand.PIP:
            pinned_package = f"{package_name}=={version}"
        case _:
            raise ValueError(f"Unsupported install command: {install_command}")
    
    return pinned_package