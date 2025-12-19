from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from cms_app import create_app


def main() -> None:
    app = create_app()

    with app.test_client() as c:
        r = c.get("/cms/explorer")
        assert r.status_code == 200
        print("GET /cms/explorer OK")

        r = c.post(
            "/cms/explorer",
            data={"dataset": "Hospitals", "states": "OR,WA", "procedure": ""},
        )
        assert r.status_code == 200
        print("POST Hospitals OK")

        r = c.get("/cms/export?dataset=Hospitals&states=OR,WA", buffered=False)
        assert r.status_code == 200
        assert (r.headers.get("Content-Type", "") or "").startswith("text/csv")
        _ = next(r.response)  # read a small chunk
        r.close()
        print("GET Hospitals export OK")

        # Doctors path (can be slower due to large national file)
        r = c.post(
            "/cms/explorer",
            data={"dataset": "Doctors", "states": "OR,WA", "procedure": "spine"},
        )
        assert r.status_code == 200
        print("POST Doctors OK")

        r = c.get("/cms/export?dataset=Doctors&states=OR,WA&procedure=spine", buffered=False)
        assert r.status_code == 200
        assert (r.headers.get("Content-Type", "") or "").startswith("text/csv")
        _ = next(r.response)  # read a small chunk
        r.close()
        print("GET Doctors export OK")

    print("Smoke test OK")


if __name__ == "__main__":
    main()
