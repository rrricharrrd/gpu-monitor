from fasthtml.common import H1, H2, Body, Div, Head, Html, P, fast_app
from pydantic import BaseModel


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


DATA = Server(
    name="foo",
    gpus=[
        GPU(index=0, name="bar", memory_used=0, memory_total=1024),
        GPU(index=1, name="baz", memory_used=1600, memory_total=2048),
    ],
)


app, rt = fast_app()


def _get_data():
    return DATA  # TODO: get real data


def _get_utilization_color(utilization):
    """Returns a Tailwind color class based on GPU memory utilization."""
    if utilization < 0.3:
        return "bg-green-500"
    elif utilization < 0.7:
        return "bg-yellow-500"
    else:
        return "bg-red-500"


def _make_html(servers):
    page = Html(
        Head("script", src="https://cdn.tailwindcss.com"),
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
                    cls="mb-6",
                )
                for server in servers
            ],
            cls="p-6 bg-gray-100",
        ),
    )
    return page


@rt("/")
def get():
    data = _get_data()
    html = _make_html([data])
    return html
