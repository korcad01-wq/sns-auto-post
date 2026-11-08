# -*- coding: utf-8 -*-
"""content_calendar.json 의 Instagram 캡션·Threads 본문을 발행 규칙으로 점검한다 (2026-11-08).

규칙 출처: 한성국 「마케팅 스킬 100」(github.com/steveaimkt/marketing-team) 중
  031 인스타그램 피드 기획 — 첫 줄 20자 훅(더보기 잘림)·인사말 금지·저장 유도 정확히 1개·해시태그 5~15개·세트 복붙 금지
  029 스레드 콘텐츠 작성  — 편당 500자·첫 줄 훅(부정 명령형/조건형/수치 반전)·본문 링크 금지·해시태그 미사용·해요체
  040 바이럴 훅 정리      — 훅 패턴 A~H 태그, 질문 단독 훅 금지(공감 후속 필수), "충격·미쳤다" 금지,
                           비율은 비교 기준을 같은 줄에, 본문이 못 갚는 숫자 금지
  gates/compliance-gate  — 최상급·보장 표현은 근거 없이 쓰지 않는다 (표시광고법 §3①1), 실존 타사 실명 비방 금지
+ 기존 규칙(쓰레드 전자책 v3): 번호 목록·9줄 초과 금지.

usage: python sns_lint.py              # 전체 점검 → insights/sns_lint_<날짜>.md + 화면 요약
       python sns_lint.py --date 2026-11-10   # 그날 나갈 글 하나만
       python sns_lint.py --strict     # 경고도 종료코드 1 (워크플로에서 막고 싶을 때)
실패(F)는 게시를 막아야 하는 것, 경고(W)는 고치면 좋은 것. 이 스크립트는 고치지 않는다 — 고치는 건 사람(또는 apply 스크립트).
"""
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
CAL = BASE / "content_calendar.json"

IG_FIRST_LINE_MAX = 30       # 031 은 20자. 폰 피드는 첫 줄 30자 안팎에서 꺾이므로 30자 초과만 경고 (20자가 목표)
IG_HASHTAG_MIN, IG_HASHTAG_MAX = 5, 15
TH_TEXT_MAX = 500            # 029 / Threads 제한
TH_LINES_MAX = 9             # 전자책 v3
TH_FIRST_LINE_MAX = 40       # 첫 줄이 길면 폰에서 두 줄로 꺾여 훅이 죽는다 (경고)

GREETING_RE = re.compile(r"^(안녕하세요|반갑습니다|씨엔씨파트너입니다|오늘은)")
SAVE_RE = re.compile(r"저장해|저장하|저장 해|저장으로|저장 버튼|저장\s*✓|📌")
SHARE_RE = re.compile(r"공유해 주|공유하시|전달해 주|전달하시")   # 저장·공유 유도 장치 (031: 정확히 1개). CTA 의 '보내주세요'는 아니다
CTA_RE = re.compile(r"DM|오픈채팅|프로필 링크|전화|댓글에")
HYPE_RE = re.compile(r"충격|미쳤|대박|경악|소름|실화")
SUPERLATIVE_RE = re.compile(r"최고|최저가|유일|업계\s*1위|국내\s*1위|1위|100\s*%|완벽|무조건|확실히|반드시\s*(통과|승인|됩니다)|보장")
RATIO_RE = re.compile(r"\d+(\.\d+)?\s*%")
RATIO_BASIS_RE = re.compile(r"대비|보다|중\s|평균|기준|가운데|에서|지난|전월|전주")
# 040 의 "비율엔 비교 기준" 은 성과 수치(조회·도달·전환이 n% 늘었다) 얘기다. 법정 요율(세액공제 25%·보험료 20% 인하)은 대상이 아니다.
PERF_CONTEXT_RE = re.compile(r"조회|도달|팔로워|전환|매출|성과|반응|상담이|문의가|늘었|줄었|올랐|떨어졌|증가|감소")
NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s", re.M)
LINK_RE = re.compile(r"https?://|www\.")
HASHTAG_LINE = lambda ln: bool(ln.strip()) and all(w.startswith("#") for w in ln.split())
FORMAL_END_RE = re.compile(r"(합니다|입니다|습니다)[.!?]?$")

# 040 훅 패턴 A~H + 전자책 v3 의 B(답할 자격형: 첫 줄에 '내가')·C(반전형: 통념을 먼저 말하고 뒤집기).
# 첫 줄 하나로 판정하므로 근사치다. 태그는 참고용, 미분류(설명형)만 경고.
HOOK_PATTERNS = [
    ("H 부정 명령형", re.compile(r"(마세요|마십시오|하지 말|않으셔도|말고)")),
    ("반전형(통념 반박)", re.compile(r"(생각하십니다|아십니다|알고 계십니다|라고요\?|줄 알|그렇지 않습니다|아닙니다|다릅니다|틀렸|틀립니다|오해|"
                                   r"라고들|하십니다|보십니다|분이 많|분이 있|회사가 많|정도로 보|몫이라고|으로 보면|이라고 보)")),
    ("B 답할 자격형(경험)", re.compile(r"(저는|제가|저한테|봐 드리|상담|만납니다|봅니다|묻습니다|찾았습니다)")),
    ("A 조건형 주장", re.compile(r"(하려면|원하면|싶으면|있다면|라면 |이라면|이면 |받으세요|부터 받|부터 보)")),
    ("수치 반전·대조", re.compile(r"\d.*(→|에서 .*로|만에|배|가 아니라)")),
    ("B 문제-해결형", re.compile(r"(막힌|걸린|떨어진|놓치|못 받|안 받|문제|고민).*(됩니다|해결|방법)")),
    ("E 결과 선언형", re.compile(r"(해 봤습니다|만들어 봤|받았습니다|나왔습니다|끝냈습니다|통과했습니다)")),
    ("F 스토리 유도형", re.compile(r"(였습니다|했었습니다|하나였습니다|있었습니다)")),
    ("D 공감 질문형", re.compile(r"\?$")),
    ("C 시간 약속형", re.compile(r"(한 줄로|한 장으로|분 안에|1분|3분)")),
    ("G 뉴스·숫자 선언", re.compile(r"^\d|\d+(명|건|원|%|점|개|억|년|일)")),
]


class Finding:
    def __init__(self, level, where, rule, detail=""):
        self.level, self.where, self.rule, self.detail = level, where, rule, detail

    def __str__(self):
        return f"[{self.level}] {self.where} · {self.rule}" + (f" — {self.detail}" if self.detail else "")


def hook_tag(first_line: str) -> str:
    for name, rx in HOOK_PATTERNS:
        if rx.search(first_line):
            return name
    return "미분류(설명형)"


def lint_ig_caption(where: str, caption: str, seen_sets: Counter) -> list:
    out = []
    lines = [ln for ln in caption.split("\n") if ln.strip()]
    if not lines:
        return [Finding("F", where, "IG 캡션 비어 있음")]
    first = lines[0].strip()
    if GREETING_RE.search(first):
        out.append(Finding("W", where, "IG 첫 줄 인사말", f"'{first[:30]}' — 첫 줄은 훅 (031)"))
    if len(first) > IG_FIRST_LINE_MAX:
        out.append(Finding("W", where, "IG 첫 줄 20자 초과", f"{len(first)}자 '{first[:40]}' — 더보기 잘림 전에 핵심 (031)"))
    body = "\n".join(ln for ln in lines if not HASHTAG_LINE(ln))
    n_save = len(SAVE_RE.findall(body)) + len(SHARE_RE.findall(body))
    if n_save == 0:
        out.append(Finding("W", where, "IG 저장·공유 유도 없음", "캡션마다 저장 유도 1개 (031)"))
    elif n_save > 1:
        out.append(Finding("W", where, "IG 저장·공유 유도 중복", f"{n_save}개 — 정확히 1개 (031)"))
    if not CTA_RE.search(body):
        out.append(Finding("W", where, "IG CTA 없음", "DM·오픈채팅·댓글 중 1개"))
    tags = [w for ln in lines if HASHTAG_LINE(ln) for w in ln.split()]
    if not (IG_HASHTAG_MIN <= len(tags) <= IG_HASHTAG_MAX):
        out.append(Finding("W", where, "IG 해시태그 개수", f"{len(tags)}개 (기준 {IG_HASHTAG_MIN}~{IG_HASHTAG_MAX}, 031)"))
    key = " ".join(sorted(tags))
    if key:
        seen_sets[key] += 1
        if seen_sets[key] > 1:
            out.append(Finding("W", where, "IG 해시태그 세트 복붙", f"같은 세트 {seen_sets[key]}번째 — 소재별로 2개 이상 바꾸기 (031)"))
    out += lint_common(where + " IG", body)
    return out


def lint_threads(where: str, text: str) -> list:
    out = []
    text = (text or "").strip()
    if not text:
        return [Finding("F", where, "Threads 본문 비어 있음")], "없음"
    lines = [ln for ln in text.split("\n") if ln.strip()]
    first = lines[0].strip()
    if len(text) > TH_TEXT_MAX:
        out.append(Finding("F", where, "Threads 500자 초과", f"{len(text)}자"))
    if len(lines) > TH_LINES_MAX:
        out.append(Finding("F", where, "Threads 9줄 초과", f"{len(lines)}줄"))
    if LINK_RE.search(text):
        out.append(Finding("F", where, "Threads 본문에 링크", "링크는 첫 답글로 (029)"))
    if any(HASHTAG_LINE(ln) for ln in lines) or re.search(r"(^|\s)#\S", text):
        out.append(Finding("F", where, "Threads 해시태그", "해시태그 미사용 (029)"))
    if NUMBERED_RE.search(text):
        out.append(Finding("F", where, "Threads 번호 목록", "번호 목록은 안 터지는 글 특징 (전자책)"))
    if len(first) > TH_FIRST_LINE_MAX:
        out.append(Finding("W", where, "Threads 첫 줄 40자 초과", f"{len(first)}자 — 폰에서 두 줄로 꺾인다"))
    tag = hook_tag(first)
    if tag == "미분류(설명형)":
        out.append(Finding("W", where, "Threads 첫 줄 훅 미분류", f"'{first[:40]}' — 부정 명령형·조건형·수치 반전·통념 반박 중 하나로 (029·040)"))
    if tag == "D 공감 질문형":
        nxt = lines[1].strip() if len(lines) > 1 else ""
        if not nxt or nxt.endswith("?"):
            out.append(Finding("W", where, "Threads 질문 단독 훅", "질문 뒤에 공감 문장 1~2줄 필수 (040 D 패턴)"))
    out += lint_common(where + " Threads", text)
    return out, tag


def lint_common(where: str, text: str) -> list:
    out = []
    m = HYPE_RE.search(text)
    if m:
        out.append(Finding("W", where, "어그로 단어", f"'{m.group(0)}' — 구체 수치·결과물로 (040)"))
    for m in SUPERLATIVE_RE.finditer(text):
        # 숫자 비교 문맥("1위는 공장등록증")은 통계가 아니라 순서 설명이지만, 근거를 한 번 보라는 뜻으로 경고만 한다
        out.append(Finding("W", where, "최상급·보장 표현", f"'{m.group(0)}' — 근거 없이 쓰지 않는다 (표시광고법 §3①1, 규제 게이트)"))
    for ln in text.split("\n"):
        if RATIO_RE.search(ln) and PERF_CONTEXT_RE.search(ln) and not RATIO_BASIS_RE.search(ln):
            out.append(Finding("W", where, "비율에 비교 기준 없음", f"'{ln.strip()[:50]}' — 무엇 대비·어느 기간인지 같은 줄에 (040)"))
    return out


def iter_items(cal: dict):
    posts = cal["posts"]
    for cat in cal["categories"]:
        p = posts[cat]
        for i, it in enumerate(p.get("card") or []):
            yield f"{cat}/card{i}", it.get("caption", ""), it.get("threads", "")
        for i, it in enumerate(p.get("question") or []):
            cap = it["text"] + "\n\n" + (it.get("hashtags") or p.get("hashtags", ""))
            yield f"{cat}/question{i}", cap, it.get("threads") or it["text"]
        for i, it in enumerate(p.get("giveaway") or []):
            cap = it["text"] + "\n\n" + (it.get("hashtags") or p.get("hashtags", ""))
            yield f"{cat}/giveaway{i}", cap, it.get("threads") or it["text"]
    for day, sp in (cal.get("specials") or {}).items():
        yield f"special {day}", sp.get("caption", ""), sp.get("threads") or sp.get("caption", "")


def main():
    cal = json.loads(CAL.read_text(encoding="utf-8-sig"))
    strict = "--strict" in sys.argv
    only_date = None
    if "--date" in sys.argv:
        only_date = date.fromisoformat(sys.argv[sys.argv.index("--date") + 1])

    findings, hooks = [], Counter()
    seen_sets = Counter()
    items = list(iter_items(cal))
    if only_date:
        sys.path.insert(0, str(BASE))
        from post_instagram import pick_todays_post
        post = pick_todays_post(cal, only_date)
        if post is None:
            print(f"{only_date}: 쉬는 날"); return 0
        items = [(f"{only_date} {post['format']}/{post['category']}", post["caption"], post["threads_text"])]

    for where, caption, threads in items:
        findings += lint_ig_caption(where, caption, seen_sets)
        res, tag = lint_threads(where, threads)
        findings += res
        hooks[tag] += 1

    fails = [f for f in findings if f.level == "F"]
    warns = [f for f in findings if f.level == "W"]
    by_rule = Counter(f.rule for f in findings)

    lines = [f"# SNS 발행 규칙 점검 · {date.today().isoformat()}",
             f"대상 {len(items)}건 · 실패 {len(fails)} · 경고 {len(warns)}", "",
             "## 규칙별 건수", "| 규칙 | 건수 |", "|---|---|"]
    lines += [f"| {r} | {n} |" for r, n in by_rule.most_common()]
    lines += ["", "## Threads 첫 줄 훅 패턴 분포 (040)", "| 패턴 | 건수 |", "|---|---|"]
    lines += [f"| {t} | {n} |" for t, n in hooks.most_common()]
    lines += ["", "## 항목별", ""]
    lines += [f"- {f}" for f in findings] or ["- 없음"]
    lines += ["", "> 출처: 마케팅 스킬 100 (031·029·040·규제 게이트) + 쓰레드 전자책 v3. 이 점검은 자동 기초 점검이며 법률 자문이 아니다."]

    out = BASE / "insights" / f"sns_lint_{date.today().isoformat()}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    print(f"대상 {len(items)}건 · 실패 {len(fails)} · 경고 {len(warns)} → {out}")
    for r, n in by_rule.most_common():
        print(f"  {n:3d}  {r}")
    print("  훅 분포:", dict(hooks))
    for f in fails:
        print(" ", f)
    return 1 if fails or (strict and warns) else 0


if __name__ == "__main__":
    sys.exit(main())
