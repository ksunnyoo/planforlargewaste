import { useState } from "react";
import { useSendFeedback, type FeedbackType } from "../api/hooks";
import type { Estimate } from "../api/types";
import { Banner, Button, Card } from "./ui";

const TYPES: { value: FeedbackType; label: string }[] = [
  { value: "wrong_item", label: "품목이 다릅니다" },
  { value: "wrong_fee", label: "수수료가 다릅니다" },
  { value: "procedure_issue", label: "배출 절차가 다릅니다" },
  { value: "other", label: "기타" },
];

export default function FeedbackCard({ estimate: e }: { estimate: Estimate }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<FeedbackType>("wrong_item");
  const [lineNo, setLineNo] = useState<number | "">("");
  const [comment, setComment] = useState("");
  const send = useSendFeedback(e.public_id);

  if (send.isSuccess) {
    return (
      <Card className="no-print">
        <Banner tone="info">의견이 접수되었습니다. 감사합니다.</Banner>
      </Card>
    );
  }

  if (!open) {
    return (
      <div className="no-print">
        <Button variant="secondary" className="w-full" onClick={() => setOpen(true)}>
          결과가 다르면 알려 주십시오
        </Button>
      </div>
    );
  }

  const showLine = type === "wrong_item" || type === "wrong_fee";

  return (
    <Card className="no-print">
      <h2 className="text-sm font-bold">오류 신고</h2>
      <p className="mt-1 text-xs text-muted">개인정보(이름, 연락처, 주소)는 입력하지 마십시오.</p>
      <div className="mt-3 space-y-3 text-sm">
        <label className="block">
          <span className="text-xs font-semibold text-muted">유형</span>
          <select
            className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2"
            value={type}
            onChange={(ev) => setType(ev.target.value as FeedbackType)}
          >
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        {showLine && (
          <label className="block">
            <span className="text-xs font-semibold text-muted">해당 품목</span>
            <select
              className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2"
              value={lineNo}
              onChange={(ev) => setLineNo(ev.target.value === "" ? "" : Number(ev.target.value))}
            >
              <option value="">전체</option>
              {e.lines.map((l) => (
                <option key={l.line_no} value={l.line_no}>
                  {l.line_no}. {l.item.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="block">
          <span className="text-xs font-semibold text-muted">내용(선택, 300자 이내)</span>
          <textarea
            className="mt-1 w-full rounded-xl border border-line px-3 py-2"
            rows={3}
            maxLength={300}
            value={comment}
            onChange={(ev) => setComment(ev.target.value)}
          />
        </label>
        {send.isError && <Banner tone="bad">{send.error.message}</Banner>}
        <div className="flex gap-2">
          <Button
            variant="primary"
            disabled={send.isPending}
            onClick={() =>
              send.mutate({
                type,
                ...(showLine && lineNo !== "" ? { line_no: lineNo } : {}),
                ...(comment.trim() ? { comment: comment.trim() } : {}),
              })
            }
          >
            {send.isPending ? "보내는 중" : "보내기"}
          </Button>
          <Button variant="secondary" onClick={() => setOpen(false)}>
            닫기
          </Button>
        </div>
      </div>
    </Card>
  );
}
