import asyncio
import logging
import os
import socket
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from fasthtml.common import H1, H2, Body, Div, Html, P, Script, fast_app
from pydantic import BaseModel

DEV = bool(int(os.environ.get("GPU_MONITOR_DEV", "0")) == 1)
if DEV:
    logging.basicConfig(force=True)
    logging.getLogger().setLevel(logging.DEBUG)
logging.debug(f"Running in DEV mode: {DEV}")

LOCALHOST = "localhost"
HOSTS_FILEPATH = Path(os.environ.get("GPU_MONITOR_HOSTS", "hosts.txt")).resolve()
HOSTS = [host.strip() for host in HOSTS_FILEPATH.read_text().strip().split("\n") if host.strip()]

SERVERS = {}
SERVERS_LOCK = asyncio.Lock()
SERVERS_TS = None


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
        return Div(
            P(f"GPU {self.index}", cls="font-bold"),
            P(self.name),
            P(f"Utilization: {self.memory_used} / {self.memory_total} MB"),
            cls=f"p-4 text-white rounded-lg {_get_utilization_color(self.utilization, self.is_reserved)}",
            id=f"{self.host}/{self.index}",
            hx_post=f"/reserve/{self.host}/{self.index}",
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


async def _refresh_data():
    global SERVERS_TS
    now = datetime.now()
    if SERVERS_TS is None or (now - SERVERS_TS) > timedelta(minutes=1):
        async with SERVERS_LOCK:
            logging.debug("Refreshing server data")
            for host in HOSTS:
                _get_host_data(host)
            SERVERS_TS = datetime.now()


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


@app.post("/reserve/{server_name}/{index}")
async def reserve(server_name: str, index: str):
    logging.debug(f"Reserving {server_name}-{index}")
    async with SERVERS_LOCK:
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
    await _refresh_data()
    async with SERVERS_LOCK:
        servers = list(SERVERS.values())
    return servers


@app.get("/")
async def get():
    await _refresh_data()
    async with SERVERS_LOCK:
        html = _make_html()
    return html
