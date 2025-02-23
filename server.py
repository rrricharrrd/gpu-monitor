import os
import socket
import subprocess

from fasthtml.common import H1, H2, Body, Div, Html, P, Script, fast_app
from pydantic import BaseModel

DEV = int(os.environ.get("GPU_MONITOR_DEV", "1")) == 1


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


DUMMY_DATA = Server(
    name="foo",
    gpus=[
        GPU(index=0, name="bar", memory_used=0, memory_total=1024),
        GPU(index=1, name="baz", memory_used=1600, memory_total=2048),
    ],
)


app, rt = fast_app(pico=False)


def _get_utilization_color(utilization):
    """Returns a Tailwind color class based on GPU memory utilization."""
    if utilization < 0.3:
        return "bg-green-500"
    elif utilization < 0.7:
        return "bg-yellow-500"
    else:
        return "bg-red-500"


def _get_data():
    if DEV:
        return [DUMMY_DATA, DUMMY_DATA]  # TODO: get real data
    else:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
        )
        gpus = []
        for line in result.stdout.strip().split("\n"):
            index, name, total_mem, used_mem = line.split(", ")
            gpus.append(
                GPU(
                    index=index,
                    name=name,
                    memory_total=int(total_mem),
                    memory_used=(used_mem),
                )
            )
        return [Server(name=socket.gethostname(), gpus=gpus)]


def _make_html(servers):
    page = Html(
        Script(src="https://cdn.tailwindcss.com"),
        Body(
            H1("GPU Monitor", cls="text-3xl font-bold mb-4"),
            *[
                Div(
                    H2(server.name, cls="text-xl font-semibold"),
                    Div(
                        *[
                            Div(
                                P(f"GPU {gpu.index}", cls="font-bold"),
                                P(gpu.name),
                                P(f"{gpu.memory_used} / {gpu.memory_total} MB"),
                                cls=f"p-4 w-40 text-white rounded-lg {_get_utilization_color(gpu.utilization)}",
                            )
                            for gpu in server.gpus
                        ],
                        cls="flex gap-4 mt-2",
                    ),
                    cls="border border-black p-6 mb-6",
                )
                for server in servers
            ],
            cls="p-4 bg-gray-100",
        ),
    )
    return page


@rt("/")
def get():
    data = _get_data()
    html = _make_html(data)
    return html
