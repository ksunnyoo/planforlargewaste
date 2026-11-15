import { Link, useParams } from "react-router-dom";
import { useEstimate } from "../api/hooks";
import EstimateView from "../components/EstimateView";
import { Button, Card, ErrorBox, Skeleton } from "../components/ui";

/** /result/:publicId (만든 직후)와 /s/:publicId (공유 보기)를 같은 컴포넌트로 보여 준다. */
export default function ResultPage({ readOnly }: { readOnly: boolean }) {
  const { publicId } = useParams();
  const { data, isPending, isError, error, refetch } = useEstimate(publicId);

  if (isPending)
    return (
      <div className="space-y-4" aria-busy="true">
        <Card><Skeleton className="mb-2 h-6 w-1/3" /><Skeleton className="h-4 w-2/3" /></Card>
        <Card><Skeleton className="h-32 w-full" /></Card>
        <Card><Skeleton className="h-20 w-full" /></Card>
      </div>
    );
  if (isError) {
    const gone = error.status === 404 || error.status === 410;
    return (
      <div className="space-y-3">
        <ErrorBox message={error.message} onRetry={gone ? undefined : () => refetch()} />
        {gone && (
          <Link to="/"><Button variant="primary">새 견적 만들기</Button></Link>
        )}
      </div>
    );
  }
  return <EstimateView estimate={data} readOnly={readOnly} />;
}
