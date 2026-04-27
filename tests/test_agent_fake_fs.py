import pytest

from llmbench.tools.base import ToolError
from llmbench.tools.fake_fs import FakeFs, build_fake_fs_tools


@pytest.mark.asyncio
async def test_read_existing_file():
    tools = build_fake_fs_tools(FakeFs(files={"a.txt": "hello"}))
    assert await tools["read_file"].run(path="a.txt") == "hello"


@pytest.mark.asyncio
async def test_read_missing_file_errors():
    tools = build_fake_fs_tools(FakeFs())
    with pytest.raises(ToolError):
        await tools["read_file"].run(path="missing.txt")


@pytest.mark.asyncio
async def test_write_creates_and_overwrites():
    fs = FakeFs(files={"a.txt": "old"})
    tools = build_fake_fs_tools(fs)
    await tools["write_file"].run(path="a.txt", content="new")
    assert fs.files["a.txt"] == "new"
    await tools["write_file"].run(path="b.txt", content="fresh")
    assert fs.files["b.txt"] == "fresh"


@pytest.mark.asyncio
async def test_list_dir_filters_by_prefix():
    fs = FakeFs(files={"src/a.py": "", "src/b.py": "", "tests/c.py": ""})
    tools = build_fake_fs_tools(fs)
    assert await tools["list_dir"].run(prefix="src/") == ["src/a.py", "src/b.py"]
    assert await tools["list_dir"].run(prefix="") == ["src/a.py", "src/b.py", "tests/c.py"]


@pytest.mark.asyncio
async def test_delete_removes_or_errors():
    fs = FakeFs(files={"a.txt": "x"})
    tools = build_fake_fs_tools(fs)
    await tools["delete_file"].run(path="a.txt")
    assert "a.txt" not in fs.files
    with pytest.raises(ToolError):
        await tools["delete_file"].run(path="a.txt")
