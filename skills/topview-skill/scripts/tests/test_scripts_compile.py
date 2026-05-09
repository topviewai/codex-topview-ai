from pathlib import Path
import py_compile
import unittest


class TopViewScriptCompileTests(unittest.TestCase):
    def test_topview_scripts_compile(self):
        scripts_dir = Path(__file__).resolve().parents[1]
        script_paths = sorted(
            path
            for path in scripts_dir.glob("*.py")
            if path.name != "__init__.py"
        )

        self.assertTrue(script_paths)

        for script_path in script_paths:
            with self.subTest(script=script_path.name):
                py_compile.compile(str(script_path), doraise=True)


if __name__ == "__main__":
    unittest.main()
