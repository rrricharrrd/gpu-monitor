import logging
import os
import socket
import subprocess
from pathlib import Path

from fasthtml.common import H1, H2, Body, Div, Html, P, Script, fast_app
from pydantic import BaseModel

LOCALHOST = "localhost"
HOSTS_FILEPATH = Path(os.environ.get("GPU_MONITOR_HOSTS", "hosts.txt")).resolve()
DEV = bool(int(os.environ.get("GPU_MONITOR_DEV", "0")) == 1)
if DEV:
    logging.basicConfig(force=True)
    logging.getLogger().setLevel(logging.DEBUG)
logging.debug(f"Running in DEV mode: {DEV}")

SERVERS = {}


class GPU(BaseModel):
    index: int
    name: str
    memory_used: int
    memory_total: int
    host: str
    is_reserved: bool = False

    @property
    def utilization(self):
        return self.memory_used / self.memory_total

    def __ft__(self):
        id = f"{self.host}___{self.index}"
        return Div(
            P(f"GPU {self.index}", cls="font-bold"),
            P(self.name),
            P(f"Utilization: {self.memory_used} / {self.memory_total} MB"),
            cls=f"p-4 text-white rounded-lg {_get_utilization_color(self.utilization, self.is_reserved)}",
            id=f"{self.host}___{self.index}",
            hx_post=f"/reserve/{id}",
            hx_trigger="click",
            hx_swap="outerHTML",
        )


class Server(BaseModel):
    name: str
    gpus: list[GPU]

    def __ft__(self):
        return Div(
            H2(self.name, cls="text-xl font-semibold"),
            Div(*self.gpus, cls="flex gap-4 mt-2"),
            cls="border border-black p-6 mb-6",
        )


app, rt = fast_app(htmlx=True, pico=False, live=DEV)


def _get_utilization_color(utilization: float, is_reserved: bool) -> str:
    """Returns a Tailwind color class based on GPU memory utilization."""
    if utilization < 0.3:
        return "bg-blue-500" if is_reserved else "bg-green-500"
    elif utilization < 0.7:
        return "bg-yellow-500"
    else:
        return "bg-red-500"


def _nvidia_smi(host: str = LOCALHOST) -> list[str]:
    try:
        if DEV:
            logging.debug(f"Loading data for {host}")
            text = Path(f"dummy-data/{host}.txt").read_text()
        else:
            command = ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total", "--format=csv,noheader,nounits"]
            if host != LOCALHOST:
                command = ["ssh", host] + command
            result = subprocess.run(command, capture_output=True, text=True)
            text = result.stdout
        return text.strip().split("\n")
    except Exception as e:
        logging.error(f"Couldn't get data for {host}: {e}")
        return []


def _get_host_data(host: str) -> None:
    global SERVERS
    hostname = host if host != LOCALHOST else socket.gethostname()
    gpus = []
    for line in _nvidia_smi(host):
        index, name, used_mem, total_mem = line.split(", ")
        gpus.append(GPU(index=index, name=name, memory_total=int(total_mem), memory_used=int(used_mem), host=hostname))
    SERVERS[hostname] = Server(name=hostname, gpus=gpus)


def _refresh_data():
    hosts = [host.strip() for host in HOSTS_FILEPATH.read_text().strip().split("\n") if host.strip()]
    logging.debug(f"Getting data for hosts {hosts}")
    for host in hosts:
        _get_host_data(host)


def _make_html():
    page = Html(
        Script(src="https://cdn.tailwindcss.com"),
        Script(src="https://unpkg.com/htmx.org@1.9.5"),
        Body(
            H1("GPU Monitor", cls="text-3xl font-bold mb-4"),
            Div(*SERVERS.values(), hx_get="/servers", hx_trigger="every 30s"),
            cls="p-4 bg-gray-100",
        ),
    )
    return page


@app.post("/reserve/{id}")
async def reserve(id: str):
    logging.debug(f"Reserving {id}")
    server_name, index = id.split("___")
    server = SERVERS.get(server_name)
    if server is not None:
        logging.debug(f"Server: {server}")
        try:
            gpu = [gpu for gpu in server.gpus if gpu.index == int(index)][0]
            gpu.is_reserved = not gpu.is_reserved  # toggle status
            logging.debug(f"New GPU status: {gpu}")
            return gpu
        except IndexError:
            pass


@app.get("/servers")
async def get_servers():
    _refresh_data()
    servers = list(SERVERS.values())
    return servers


@app.get("/")
async def get():
    _refresh_data()
    html = _make_html()
    return html
