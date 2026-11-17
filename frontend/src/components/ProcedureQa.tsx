import { useState } from "react";
import { useAskProcedure } from "../api/hooks";
import { dateKo } from "../lib/format";
import { Banner, Button, Card, ErrorBox } from "./ui";

const EXAMPLE_QUESTIONS = ["배출 신고는 어떻게 합니까?", "신고 후 접수번호는 어디에 붙입니까?"];

/** 배출 절차 질문창. 안내문에 근거가 있을 때만 답하고, 근거가 없으면 답하지 않는다. 질문은 저장하지 않는다. */
export default function ProcedureQa({ code, procedureSupported }: { code: string | null; procedureSupported: boolean }) {
  const [question, setQuestion] = useState("");
  const ask = useAskProcedure();

  if (!code) return null;

  if (!procedureSupported)
    return (
      <Card>
        <p className="text-sm font-bold">배출 절차 질문</p>
        <p className="mt-1 text-sm text-muted">이 지역은 수수료만 제공합니다. 절차는 해당 지자체의 안내를 확인하십시오.</p>
      </Card>
    );

  function submit(q: string) {
    const text = q.trim();
    if (!code || !text || ask.isPending) return;
    ask.mutate({ municipality_code: code, question: text });
  }

  const res = ask.data;
  return (
    <Card className="no-print">
      <label htmlFor="qa-in" className="text-sm font-bold">
        배출 절차에 대해 질문하십시오.
      </label>
      <p className="mt-1 text-xs text-muted">지자체 안내문에 근거가 있는 내용만 답합니다. 주소와 연락처는 입력하지 마십시오.</p>
      <form
        className="mt-2 flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <input
          id="qa-in"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={200}
          placeholder="예: 배출 신고는 어떻게 합니까?"
          className="min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm"
        />
        <Button type="submit" disabled={!question.trim() || ask.isPending} className="shrink-0">
          {ask.isPending ? "확인 중…" : "질문하기"}
        </Button>
      </form>
      <div className="mt-2 flex flex-wrap gap-2">
        {EXAMPLE_QUESTIONS.map((q) => (
          <Button
            key={q}
            variant="ghost"
            disabled={ask.isPending}
            onClick={() => {
              setQuestion(q);
              submit(q);
            }}
          >
            {q}
          </Button>
        ))}
      </div>

      {ask.isError && <div className="mt-3"><ErrorBox message={ask.error.message} onRetry={() => submit(question)} /></div>}

      {res && (
        <div className="mt-3 space-y-2" aria-live="polite">
          {res.answerable ? (
            <div className="rounded-xl border border-line p-3">
              <p className="whitespace-pre-line text-sm">{res.answer}</p>
              {res.citations.length > 0 && (
                <ul className="mt-2 space-y-1 border-t border-line pt-2 text-xs text-muted">
                  <li className="font-semibold">근거</li>
                  {res.citations.map((c) => (
                    <li key={c.chunk_id}>
                      {c.source_name} · {c.section} · {c.base_date ? `기준일 ${dateKo(c.base_date)}` : "기준일 미확인"}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <Banner tone="info">{res.answer}</Banner>
          )}
          <p className="text-xs text-muted">{res.disclaimer}</p>
        </div>
      )}
    </Card>
  );
}
