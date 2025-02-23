from pydantic import BaseModel
from fasthtml.common import fast_app, Titled, P, serve


class GPU(BaseModel):
    index: int
    memory_used: int
    memory: int


class Server(BaseModel):
    name: str
    gpus: list[GPU]

DATA = Server(name="foo", gpus=[GPU(index=0, memory_used=0, memory=1024), GPU(index=0, memory_used=1600, memory=2048)])


app, rt = fast_app()

@rt("/")
def get():
    return Titled("GPU Monitor", P(DATA.model_dump_json()))

serve()
