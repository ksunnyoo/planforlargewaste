# 개발 시작 안내서 (VS Code, 처음부터 순서대로)

> 대상: 로컬 PC의 VS Code에서 개발하는 사용자. 명령어는 VS Code 터미널(`Ctrl + ~`)에 한 줄씩 붙여 넣습니다.
> 표기: `PS>` 는 Windows PowerShell, 이외는 모든 운영체제 공통입니다.

## 0. 설치할 것 (한 번만)
| 프로그램 | 확인 명령 | 없으면 |
|---|---|---|
| Git | `git --version` | https://git-scm.com 에서 설치 |
| uv(파이썬 도구) | `uv --version` | Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` / Mac·Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh` 실행 후 **VS Code를 껐다 켭니다** |

파이썬 3.13은 따로 설치하지 않습니다. `uv sync`가 자동으로 설치합니다.

## 1. 저장소 받기
VS Code 터미널에서 (바탕화면에서 시작하는 예):
```
cd Desktop
git clone https://github.com/ksunnyoo/planforlargewaste.git
cd planforlargewaste
code .
```
`code .`가 안 되면 VS Code 메뉴 `파일 > 폴더 열기`로 `planforlargewaste` 폴더를 엽니다. 이후 모든 명령은 이 폴더(저장소 최상위)의 터미널에서 실행합니다.

## 2. 파일을 둘 위치 (최종 폴더 구조)
빈 폴더가 없으면 VS Code 탐색기에서 `새 폴더`로 만듭니다. 받은 파일을 **탐색기로 끌어다 놓으면** 됩니다.

```
planforlargewaste/
├─ README.md                      ← 받은 파일
├─ .gitignore                     ← 받은 파일 (이미 있으면 덮어쓰기)
├─ .env.example                   ← 받은 파일
├─ docs/
│  ├─ 01_PRD.md  02_SDD.md  03_API_PLAN.md  04_API_SPEC.md
│  ├─ 05_ARCHITECTURE.md  06_EVAL_PLAN.md  07_DATA_TERMS.md  08_DEV_GUIDE.md   ← 받은 파일
│  └─ research/
│     ├─ interviews.md            ← 받은 파일
│     └─ data_check.md            ← 받은 파일(스크립트가 다시 만들어 줌)
├─ db/
│  └─ schema.sql                  ← 받은 파일
├─ scripts/
│  ├─ extract_seongnam_pdf.py     ← 받은 파일
│  ├─ prepare_data.py             ← 받은 파일
│  └─ load_to_db.py               ← 받은 파일
├─ data/
│  ├─ raw/
│  │  ├─ national_fees.csv        ← 사용자가 내려받은 전국 CSV (이름을 바꿔서 넣기, 3-1 참조)
│  │  ├─ seongnam_fee_table.pdf   ← 사용자가 준 성남시 별표 PDF (이름을 바꿔서 넣기, 선택)
│  │  └─ seongnam_procedure.md    ← 받은 파일
│  └─ processed/
│     ├─ seongnam_fees.csv        ← 받은 파일
│     ├─ seongnam_fees_misc.csv   ← 받은 파일
│     ├─ seongnam_fees.README.md  ← 받은 파일
│     └─ seongnam_rules.md        ← 받은 파일
└─ backend/
   ├─ pyproject.toml              ← 받은 파일
   ├─ .env                        ← 직접 만듦(5단계). 절대 커밋하지 않음
   ├─ app/
   │  ├─ __init__.py              ← 빈 파일(아래 3-2)
   │  ├─ main.py                  ← 받은 파일
   │  ├─ core/
   │  │  ├─ __init__.py           ← 빈 파일
   │  │  └─ config.py             ← 받은 파일
   │  ├─ services/
   │  │  ├─ __init__.py           ← 빈 파일
   │  │  └─ fee_calculator.py     ← 받은 파일
   │  └─ api/
   │     ├─ __init__.py           ← 빈 파일
   │     └─ v1/
   │        └─ __init__.py        ← 빈 파일
   └─ tests/
      ├─ test_fee_calculator.py   ← 받은 파일
      └─ test_health.py           ← 받은 파일
```

### 3-1. 전국 CSV 이름 바꾸기
데이터포털에서 받은 CSV(한글 이름)를 `data/raw/` 폴더에 넣고, 파일 이름을 `national_fees.csv`로 바꿉니다(탐색기에서 우클릭 > 이름 바꾸기). 성남시 별표 PDF는 `seongnam_fee_table.pdf`로 바꿔 같은 폴더에 둡니다. 이 파일들은 `.gitignore`에 있어 GitHub에 올라가지 않습니다.

### 3-2. 빈 파일 `__init__.py` 만들기
VS Code 터미널에서 한 번에 만들 수 있습니다.
- Windows PowerShell:
```
New-Item backend/app/__init__.py, backend/app/core/__init__.py, backend/app/services/__init__.py, backend/app/api/__init__.py, backend/app/api/v1/__init__.py -ItemType File -Force
```
- Mac·Linux:
```
touch backend/app/__init__.py backend/app/core/__init__.py backend/app/services/__init__.py backend/app/api/__init__.py backend/app/api/v1/__init__.py
```
(폴더가 없다는 오류가 나면 먼저 `backend/app/core` 등을 탐색기에서 만든 뒤 다시 실행합니다.)

## 4. 서버 환경 만들고 테스트 실행
```
cd backend
uv sync
uv run pytest
```
`14 passed`가 나오면 정상입니다. `uv sync`는 처음에 몇 분 걸릴 수 있습니다.

서버 실행(확인 후 `Ctrl + C`로 종료):
```
uv run uvicorn app.main:app --reload
```
브라우저에서 `http://127.0.0.1:8000/health` 를 열면 `{"status":"ok", ...}`가 보이고, `http://127.0.0.1:8000/docs` 에서 자동 문서 화면이 열립니다.

```
cd ..
```
(저장소 최상위로 돌아옵니다.)

## 5. 데이터 정제 (DB 없이 가능)
저장소 최상위에서:
```
uv run --project backend python scripts/prepare_data.py --national data/raw/national_fees.csv --seongnam data/processed/seongnam_fees.csv --misc data/processed/seongnam_fees_misc.csv
```
정상이면 아래가 출력됩니다(숫자는 2026-11-13 기준).
```
입력 행: 23382 (전국 23186, 성남시 196)
적재 행(waste_items): 23326 / 지자체 144곳 / 카탈로그 12883건
fee_type 분포: {'paid': 22667, 'free': 608, 'exempt': 51}
```
만들어지는 파일: `data/processed/municipalities.csv`, `item_catalog.csv`, `waste_items.csv`, `docs/research/data_check.md`.

## 6. Supabase(무료 DB) 만들기
1. https://supabase.com 가입 후 `New project` 생성. 프로젝트 이름 아무거나, **데이터베이스 비밀번호를 정하고 따로 적어 둡니다**. 리전은 Seoul이 있으면 선택합니다.
2. 프로젝트가 만들어지면 위쪽 `Connect` 버튼을 눌러 **Session pooler** 연결 문자열(`postgresql://...`)을 복사합니다. 무료 플랜의 직접 연결은 IPv6만 지원하는 경우가 있어 pooler를 권장합니다 **[검증 필요: 화면 이름은 바뀔 수 있음]**.
3. 문자열 안의 `[YOUR-PASSWORD]` 자리를 정한 비밀번호로 바꿉니다. 비밀번호에 특수문자(`@`, `#`, `/`)가 있으면 영문·숫자로 다시 정하는 편이 안전합니다.
4. 문자열 맨 앞 `postgresql://` 를 `postgresql+psycopg://` 로 고칩니다.

## 7. `.env` 파일 만들기
`.env.example`을 복사해 `backend/.env`로 만듭니다.
- Windows PowerShell: `Copy-Item .env.example backend/.env`
- Mac·Linux: `cp .env.example backend/.env`

`backend/.env`를 열어 `DATABASE_URL=` 뒤에 6단계의 문자열을 붙여 넣고 저장합니다. 이 파일은 `.gitignore`에 있어 올라가지 않으며, **키·비밀번호를 채팅이나 GitHub에 보내지 마십시오.**

## 8. DB에 적재
```
uv run --project backend python scripts/load_to_db.py
```
정상이면 `적재 완료: municipalities 144, item_catalog 12883, waste_items 23326`이 출력됩니다. 처음 실행 때 `db/schema.sql`도 자동으로 실행됩니다.
- `waste_items에 이미 ... 있습니다` → 다시 적재하려면 끝에 ` --reset`을 붙입니다.
- 접속 오류가 나면 6단계 2~4번(비밀번호, `postgresql+psycopg://`)을 확인합니다.
- Supabase 화면 `Table Editor`에서 `municipalities`, `waste_items` 표가 보이면 성공입니다.

## 9. GitHub에 올리기(커밋)
```
git status
git add .
git commit -m "docs: 기획 문서 7종, 데이터 정제, 수수료 계산기, DB 스키마"
git push
```
- `git status`에서 `.env`나 `data/raw/*.csv`가 **보이면** 올리지 말고 중단합니다(원래는 보이지 않아야 합니다).
- 처음 push는 GitHub 로그인 창이 열릴 수 있습니다.

## 10. 자주 나는 오류
| 증상 | 해결 |
|---|---|
| `uv`를 찾을 수 없음 | 설치 후 VS Code를 완전히 껐다 켭니다 |
| `ModuleNotFoundError: app` (pytest) | `backend` 폴더 안에서 실행했는지, `__init__.py` 5개가 있는지 확인 |
| 한글이 깨져 보임 | 파일이 UTF-8인지 확인(VS Code 오른쪽 아래 인코딩 표시) |
| 데이터 정제에서 `FileNotFoundError` | `data/raw/national_fees.csv` 이름과 위치 확인 |
| `extension "vector" ... not available` | Supabase 대시보드 `Database > Extensions`에서 `vector`를 켠 뒤 다시 실행 |

## 11. 다음 개발 (이 안내서 이후)
1. 11/16(월): API-02 지자체 목록, API-03 품목 검색(trigram), 품목 매칭
2. 11/17(화): 절차 RAG, 견적 생성 API, 프론트 화면
3. 11/18(수): 프론트 마무리, 평가, 배포 / 11/19(목): 점검·시연

각 단계의 코드는 제가 이 방식(파일을 만들어 전달 + 위치와 실행 명령 안내)으로 계속 드립니다.
