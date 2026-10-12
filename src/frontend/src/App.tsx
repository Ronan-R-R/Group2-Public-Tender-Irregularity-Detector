import { Shell } from "./components/Shell";
import { EmptyBlock, PageTitle } from "./components/ui";
import { Buyer } from "./pages/Buyer";
import { Overview } from "./pages/Overview";
import { TenderDetail } from "./pages/TenderDetail";
import { Tenders } from "./pages/Tenders";
import { Link, href, useRoute } from "./router";

export function App() {
  const route = useRoute();
  return (
    <Shell route={route}>
      {route.name === "overview" && <Overview />}
      {route.name === "tenders" && <Tenders search={route.search} />}
      {route.name === "tender" && <TenderDetail key={route.id} id={route.id} />}
      {route.name === "buyer" && <Buyer key={route.id} id={route.id} />}
      {route.name === "not-found" && (
        <>
          <PageTitle>Page not found</PageTitle>
          <EmptyBlock title="This address does not match any page.">
            <Link to={href.overview()} className="underline">Go to the overview</Link>
          </EmptyBlock>
        </>
      )}
    </Shell>
  );
}
