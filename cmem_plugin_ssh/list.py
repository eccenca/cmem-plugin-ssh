"""SSH List files task plugin"""

from collections.abc import Sequence

import paramiko
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginAction, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities, Entity, EntityPath, EntitySchema
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.password import Password, PasswordParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.retrieval import SSHRetrieval
from cmem_plugin_ssh.utils import AUTHENTICATION_CHOICES, load_private_key


def generate_schema() -> EntitySchema:
    """Provide the schema for files"""
    return EntitySchema(
        type_uri="",
        paths=[
            EntityPath(path="file_name"),
            EntityPath(path="size"),
            EntityPath(path="uid"),
            EntityPath(path="gid"),
            EntityPath(path="mode"),
            EntityPath(path="atime"),
            EntityPath(path="mtime"),
        ],
    )


@Plugin(
    label="List SSH files",
    plugin_id="cmem_plugin_ssh-List",
    description="SSH list files",
    documentation="""
    """,
    icon=Icon(package=__package__, file_name="ssh-icon.svg"),
    actions=[
        PluginAction(
            name="preview_results",
            label="Preview results (max. 10)",
            description="Lists 10 files as a preview.",
        )
    ],
    parameters=[
        PluginParameter(
            name="hostname",
            label="Hostname",
            description="Hostname to connect to.Usually in the form of an IP address",
        ),
        PluginParameter(
            name="port",
            label="Port",
            description="The port on which the connection will be tried on. Default is 22.",
            default_value=22,
        ),
        PluginParameter(
            name="username",
            label="Username",
            description="The username of which a connection will be instantiated.",
        ),
        PluginParameter(
            name="authentication_method",
            label="Authentication method",
            description="The method that is used to connect to the SSH server.",
            param_type=ChoiceParameterType(AUTHENTICATION_CHOICES),
        ),
        PluginParameter(
            name="private_key",
            label="Private key",
            description="Your private key to connect via SSH.",
            param_type=PasswordParameterType(),
            default_value="",
        ),
        PluginParameter(
            name="password",
            label="Password",
            description="Depending on your authentication method this will either be used to"
            "connect via password to SSH or is used to decrypt the SSH private key",
            param_type=PasswordParameterType(),
            default_value="",
        ),
        PluginParameter(
            name="path",
            label="Path",
            description="The currently selected path withing your SSH instance.",
            default_value="",
            param_type=DirectoryParameterType("directories", "Folder"),
        ),
        PluginParameter(
            name="regex",
            label="Regular expression",
            description="A regular expression used to define which files will get listed.",
            default_value="^.*$",
        ),
        PluginParameter(
            name="no_subfolder",
            label="No subfolder",
            description="When this flag is set, only files from the current directory "
            "will be listed.",
            default_value=False,
        ),
    ],
)
class ListFiles(WorkflowPlugin):
    """List Plugin SSH"""

    def __init__(  # noqa: PLR0913
        self,
        hostname: str,
        port: int,
        username: str,
        authentication_method: str,
        private_key: str | Password,
        password: str | Password,
        path: str,
        no_subfolder: bool,
        regex: str = "",
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.authentication_method = authentication_method
        self.private_key = private_key
        self.password = password if isinstance(password, str) else password.decrypt()
        self.path = path
        self.no_subfolder = no_subfolder
        self.regex = rf"{regex}"
        self.input_ports = FixedNumberOfInputs([])
        self.output_port = FixedSchemaPort(schema=generate_schema())

        # dont think actually connecting is necessary here
        self.ssh_client = paramiko.SSHClient()
        self.connect_ssh_client()
        self.sftp = self.ssh_client.open_sftp()

    def close_connections(self) -> None:
        """Close connection from sftp and ssh"""
        self.sftp.close()
        self.ssh_client.close()

    def connect_ssh_client(self) -> None:
        """Connect to the ssh client with the selected authentication method"""
        if self.authentication_method == "key":
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.hostname,
                username=self.username,
                pkey=load_private_key(self.private_key, self.password),
                port=self.port,
            )
        elif self.authentication_method == "password":
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                port=self.port,
            )

    def preview_results(self) -> str:
        """Preview the results of an execution"""
        retrieval = SSHRetrieval(
            ssh_client=self.ssh_client,
            no_subfolder=self.no_subfolder,
            regex=self.regex,
        )
        files = retrieval.list_files_parallel(
            files=[], context=None, path=self.path, no_of_max_hits=10
        )
        output = [f"The Following {len(files)} entities were found:", ""]
        output.extend(f"- {file.filename}" for file in files)
        return "\n".join(output)

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> Entities:
        """Execute the workflow task"""
        _ = inputs
        context.report.update(
            ExecutionReport(entity_count=0, operation="wait", operation_desc="files listed.")
        )
        entities = []

        retrieval = SSHRetrieval(
            ssh_client=self.ssh_client,
            no_subfolder=self.no_subfolder,
            regex=self.regex,
        )
        files = retrieval.list_files_parallel(files=[], context=context, path=self.path)
        context.report.update(
            ExecutionReport(
                entity_count=len(files), operation="wait", operation_desc="files listed."
            )
        )

        for file in files:
            entities.append(
                Entity(
                    uri=file.filename,
                    values=[
                        [file.filename],
                        [str(file.st_size)],
                        [str(file.st_uid)],
                        [str(file.st_gid)],
                        [str(file.st_mode)],
                        [str(file.st_atime)],
                        [str(file.st_mtime)],
                    ],
                )
            )
            context.report.update(
                ExecutionReport(
                    entity_count=len(entities),
                    operation="write",
                    operation_desc="entities generated",
                )
            )

        context.report.update(
            ExecutionReport(
                entity_count=len(entities),
                operation="done",
                operation_desc="entities generated",
                sample_entities=Entities(entities=iter(entities[:10]), schema=generate_schema()),
            )
        )

        self.close_connections()

        return Entities(
            entities=iter(entities),
            schema=generate_schema(),
        )
