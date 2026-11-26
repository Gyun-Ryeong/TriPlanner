"""
로컬 MariaDB(triplanner) → AWS RDS MySQL 에 넣을 덤프 만들기.

MariaDB 덤프 중 MySQL이 못 읽는 부분만 고친다.
  1. 첫 줄 '/*M!999999\\- enable the sandbox mode */'  → 지움 (mysql 클라이언트가 오류를 냄)
  2. embedding vector(384)                            → varbinary(1536)  (float32 384개 = 1536바이트, 코드는 바이트로 읽음)
  3. VECTOR KEY … 인덱스                               → 지움 (장소 검색은 이 인덱스를 쓰지 않음)
벡터는 --hex-blob 으로 16진수로 저장해서 깨지지 않는다.

    python deploy/make_mysql_dump.py                       # → deploy/triplanner_mysql.sql
    python deploy/make_mysql_dump.py --out D:/dump.sql

DB 접속 정보는 rag_project/.env 의 DB_HOST·DB_PORT·DB_NAME·DB_USER·DB_PASSWORD 를 쓴다.
결과 파일에는 회원 정보가 들어 있으니 깃에 올리지 않는다 (*.sql 은 .gitignore 에 있음).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DUMP = r"C:\Program Files\MariaDB 11.8\bin\mariadb-dump.exe"

SANDBOX_RE = re.compile(r"^/\*M!999999\\- enable the sandbox mode \*/.*\n?", re.M)
VECTOR_COL_RE = re.compile(r"\bvector\((\d+)\)", re.I)
VECTOR_KEY_RE = re.compile(r",\n\s*VECTOR KEY [^\n]*(?=\n\))", re.I)


def read_env(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def convert(sql: str) -> tuple[str, dict]:
    """MariaDB 덤프 문자열 → MySQL에서 읽히는 문자열. 무엇을 몇 번 바꿨는지도 돌려준다."""
    counts = {}
    sql, counts["sandbox"] = SANDBOX_RE.subn("", sql)
    sql, counts["vector_key"] = VECTOR_KEY_RE.subn("", sql)
    sql, counts["vector_col"] = VECTOR_COL_RE.subn(lambda m: f"varbinary({int(m.group(1)) * 4})", sql)
    return sql, counts


def main(argv):
    ap = argparse.ArgumentParser(description="로컬 MariaDB → RDS MySQL용 덤프")
    ap.add_argument("--out", default=str(ROOT / "deploy" / "triplanner_mysql.sql"))
    ap.add_argument("--mariadb-dump", default=shutil.which("mariadb-dump") or DEFAULT_DUMP)
    args = ap.parse_args(argv)

    env = read_env(ROOT / "rag_project" / ".env")
    for key in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        if not env.get(key):
            sys.exit(f"rag_project/.env 에 {key} 가 없어요.")
    if not Path(args.mariadb_dump).exists():
        sys.exit(f"mariadb-dump 를 찾지 못했어요: {args.mariadb_dump}  (--mariadb-dump 로 경로를 알려 주세요)")

    cmd = [args.mariadb_dump, "-h", env["DB_HOST"], "-P", env["DB_PORT"], "-u", env["DB_USER"],
           "--single-transaction", "--hex-blob", "--default-character-set=utf8mb4", "--routines=false", env["DB_NAME"]]
    print("덤프 중… (장소 벡터가 있어 1~2분 걸려요)")
    run = subprocess.run(cmd, capture_output=True, env={**os.environ, "MYSQL_PWD": env["DB_PASSWORD"]})
    if run.returncode != 0:
        sys.exit("mariadb-dump 실패: " + run.stderr.decode("utf-8", "replace")[:500])
    sql, counts = convert(run.stdout.decode("utf-8"))

    tables = re.findall(r"CREATE TABLE `([^`]+)`", sql)
    rows = {}
    current = None
    for line in sql.splitlines():
        if line.startswith("INSERT INTO `"):
            current = line.split("`")[1]
        elif line.startswith("(") and current:
            rows[current] = rows.get(current, 0) + 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sql, encoding="utf-8")

    print(f"저장: {out} ({out.stat().st_size / 1e6:.0f}MB)")
    print(f"고친 곳: 첫 줄 {counts['sandbox']}, VECTOR 열 {counts['vector_col']}, VECTOR 인덱스 {counts['vector_key']}")
    print(f"테이블 {len(tables)}개: " + ", ".join(f"{t} {rows.get(t, 0)}행" for t in tables))
    left = [w for w in ("vector(", "VECTOR KEY", "sandbox mode") if w.lower() in sql.lower()]
    print("MySQL에서 안 읽히는 부분이 남아 있어요: " + ", ".join(left) if left else "MySQL에서 안 읽히는 부분 없음 ✅")


if __name__ == "__main__":
    main(sys.argv[1:])
