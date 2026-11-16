import { useNavigate } from "react-router-dom";
import { useCreateEstimate } from "../api/hooks";
import DraftList from "../components/DraftList";
import ItemSearch from "../components/ItemSearch";
import TextParse from "../components/TextParse";
import MunicipalityPicker from "../components/MunicipalityPicker";
import { Banner, ErrorBox } from "../components/ui";
import { useDraftStore } from "../store/draftStore";

export default function InputPage() {
  const navigate = useNavigate();
  const code = useDraftStore((s) => s.municipalityCode);
  const lines = useDraftStore((s) => s.lines);
  const create = useCreateEstimate();

  function submit() {
    if (!code || lines.length === 0) return;
    create.mutate(
      {
        municipality_code: code,
        lines: lines.map((l) => ({
          raw_text: l.name,
          item_id: l.itemId,
          quantity: l.quantity,
          operator_fee_won: l.operatorFeeWon,
        })),
      },
      { onSuccess: (est) => navigate(`/result/${est.public_id}`) },
    );
  }

  return (
    <div className="space-y-4">
      <Banner tone="info" title="주소와 연락처는 입력하지 마십시오.">
        버리실 물건을 검색해 담으면 지자체 수수료를 계산합니다.
      </Banner>
      <MunicipalityPicker />
      <TextParse />
      <ItemSearch />
      {code && <DraftList onSubmit={submit} submitting={create.isPending} />}
      {create.isError && <ErrorBox message={create.error.message} onRetry={submit} />}
    </div>
  );
}
