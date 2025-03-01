import logging
import os
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


class GPU(BaseModel):
    index: int
    name: str
    memory_used: int
    memory_total: int

    @property
    def utilization(self):
        return self.memory_used / self.memory_total


class Server(BaseModel):
    name: str
    gpus: list[GPU]


app, rt = fast_app(htmlx=True, pico=False, live=DEV)


def _get_utilization_color(utilization: float) -> str:
    """Returns a Tailwind color class based on GPU memory utilization."""
    if utilization < 0.3:
        return "bg-green-500"
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


def _get_host_data(host: str) -> Server:
    gpus = []
    for line in _nvidia_smi(host):
        index, name, used_mem, total_mem = line.split(", ")
        gpus.append(GPU(index=index, name=name, memory_total=int(total_mem), memory_used=int(used_mem)))
    return Server(name=host, gpus=gpus)


def _get_data() -> list[Server]:
    hosts = [host.strip() for host in HOSTS_FILEPATH.read_text().strip().split("\n") if host.strip()]
    logging.debug(f"Getting data for hosts {hosts}")
    return [_get_host_data(host) for host in hosts]


def _make_servers_html(servers: list[Server]):
    return [
        Div(
            H2(server.name, cls="text-xl font-semibold"),
            Div(
                *[
                    Div(
                        P(f"GPU {gpu.index}", cls="font-bold"),
                        P(gpu.name),
                        P(f"Utilization: {gpu.memory_used} / {gpu.memory_total} MB"),
                        cls=f"p-4 text-white rounded-lg {_get_utilization_color(gpu.utilization)}",
                    )
                    for gpu in server.gpus
                ],
                cls="flex gap-4 mt-2",
            ),
            cls="border border-black p-6 mb-6",
        )
        for server in servers
    ]


def _make_html(servers: list[Server]):
    page = Html(
        Script(src="https://cdn.tailwindcss.com"),
        Script(src="https://unpkg.com/htmx.org@1.9.5"),
        Body(
            H1("GPU Monitor", cls="text-3xl font-bold mb-4"),
            Div(*_make_servers_html(servers), hx_get="/servers", hx_trigger="every 5s"),
            cls="p-4 bg-gray-100",
        ),
    )
    return page


@rt("/servers")
def get_servers():
    data = _get_data()
    html = _make_servers_html(data)
    return html


@rt("/")
def get():
    data = _get_data()
    html = _make_html(data)
    return html
