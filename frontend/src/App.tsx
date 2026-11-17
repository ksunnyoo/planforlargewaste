import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HashRouter, Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Button } from "./components/ui";
import EvaluationPage from "./pages/EvaluationPage";
import InputPage from "./pages/InputPage";
import ResultPage from "./pages/ResultPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function NotFound() {
  return (
    <div className="py-10 text-center">
      <p className="text-sm text-muted">페이지를 찾을 수 없습니다.</p>
      <Link to="/"><Button className="mt-4">처음으로</Button></Link>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* GitHub Pages에서 새로고침 404를 피하려고 HashRouter를 쓴다. */}
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<InputPage />} />
            <Route path="/result/:publicId" element={<ResultPage readOnly={false} />} />
            <Route path="/evaluation" element={<EvaluationPage />} />
            <Route path="/s/:publicId" element={<ResultPage readOnly />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </HashRouter>
    </QueryClientProvider>
  );
}
