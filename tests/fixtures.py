"""Test fixtures for SSH docker container"""

SSH_HOSTNAME = "localhost"
SSH_PORT = 2222
SSH_USERNAME = "testuser"
SSH_PASSWORD = "testpassword"  # noqa: S105
SSH_PRIVATE_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
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
zTguSYx11V0AAAAFbHdATFcBAgMEBQY=
-----END OPENSSH PRIVATE KEY-----"""

SSH_PRIVATE_KEY_WITH_PASSWORD = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAACmFlczI1Ni1jdHIAAAAGYmNyeXB0AAAAGAAAABBIyXE/Gp
tHgq29kF4X0ez9AAAAEAAAAAEAAAAzAAAAC3NzaC1lZDI1NTE5AAAAIPwT3TNp+EPAmvps
CmFzJRdSkRukqClAoBmwIqcHxu5UAAAAkDf+jA4Ef8qD0/WJw+E3whaqMJbc7R4uv5dT72
BcvmPzFLPIhw41FBbdWhGA9xXVunYrvtE/tSsFCulN+MxviwDqmCwlUy1eldy6GuSwSgEL
fN/iuUSMI79AkamY/0V9o216luN2tPHwvUAZD76mkIZvmIt6pdNqI6DQhGPSvtYiqf0evr
tR1x7eHFKp+StcVA==
-----END OPENSSH PRIVATE KEY-----"""  # noqa: S105
