import type { ReactNode } from "react";
import { PageTitle } from "../components/ui";
import { Link, href, usePageFocus } from "../router";

// Keep these pages in step with what the site actually does. A notice that
// describes data flows the code does not have is a liability, not cover.

export const CONTACT_EMAIL = "20230294@ctucareer.co.za";
const UPDATED = "12 October 2026";
const TEAM = "CTU SE2 Capstone Group 2 (Eugene, Michael, Sebastian, Ronan and Nhlanhla)";

function Prose({ children }: { children: ReactNode }) {
  return <div className="legal max-w-3xl">{children}</div>;
}

function Mail() {
  return (
    <a className="underline" href={`mailto:${CONTACT_EMAIL}`}>
      {CONTACT_EMAIL}
    </a>
  );
}

export function Privacy() {
  usePageFocus("privacy");
  return (
    <>
      <PageTitle eyebrow={`Last updated ${UPDATED}`}>Privacy notice</PageTitle>
      <Prose>
        <p>
          This notice explains what personal information the Tender Risk Monitor processes, why, and what you can do about it.
          It follows the Protection of Personal Information Act 4 of 2013 (POPIA).
        </p>

        <h2>Who is responsible</h2>
        <p>
          The site is run by {TEAM}, students at CTU Training Solutions, Boksburg, as a capstone project. It is not an official
          service of CTU Training Solutions, National Treasury or the Companies and Intellectual Property Commission (CIPC).
          Contact us about anything in this notice at <Mail />.
        </p>

        <h2>What we process</h2>
        <h3>Public procurement records</h3>
        <p>
          The dashboard is built from award data that National Treasury publishes through its eTenders portal, which we take
          from the Open Contracting Data Standard feed released under the Public Domain Dedication and License (PDDL). The
          records name buyers and winning suppliers, and the value and dates of each award. Where a supplier trades as a sole
          proprietor, its name is personal information.
        </p>
        <p>
          The feed also contains the names, email addresses and phone numbers of procurement officials. Our loader never reads
          those fields, and they are not stored or shown anywhere.
        </p>
        <h3>Technical logs</h3>
        <p>
          Our host, Cloudflare, processes your IP address, browser details and the pages you request in order to deliver the
          site and protect it from abuse. We do not run analytics, advertising or tracking of any kind.
        </p>
        <h3>Planned: company director data</h3>
        <p>
          Some red-flag rules need company and director records from CIPC. These are not processed yet. When they are, director
          names and related details will be kept in a private database, used only to evaluate those rules, and never published
          on this site: the dashboard shows only pseudonymous director references and counts. We will update this notice before
          that processing starts.
        </p>

        <h2>Why, and our lawful basis</h2>
        <ul>
          <li>
            <strong>Procurement records</strong> are processed for public-interest research into the transparency of public
            procurement, and for the assessment of our capstone project. The lawful basis is our legitimate interests and those
            of the public (POPIA section 11(1)(f)). The records come from a public record, which section 12(2)(a) allows us to
            use without collecting them from you directly.
          </li>
          <li>
            <strong>Technical logs</strong> are processed to deliver the site and keep it secure, also under section 11(1)(f).
          </li>
        </ul>
        <p>We do not sell personal information or use it for marketing, and we do not make decisions about anyone.</p>

        <h2>Risk scores about a supplier</h2>
        <p>
          Scores are produced automatically from published records. A red flag means a pattern worth reviewing, not a finding
          of wrongdoing. If a score concerns you or your business and you think the underlying record is wrong, email <Mail />{" "}
          with the award reference shown on the tender page and we will review it.
        </p>

        <h2>Who we share it with</h2>
        <ul>
          <li>Cloudflare, which hosts the site.</li>
          <li>GitHub, which stores our source code and runs the job that builds the scores.</li>
          <li>Supabase, which will host the private database once director data is added.</li>
        </ul>
        <p>
          These providers process information outside South Africa. We rely on their binding data-processing terms as the basis
          for those transfers (POPIA section 72(1)(a)).
        </p>

        <h2>How long we keep it</h2>
        <ul>
          <li>Procurement records: for as long as the project runs, because price comparisons look back 24 months.</li>
          <li>Director data, once added: deleted 12 months after its last link to an award we still hold.</li>
          <li>Technical logs: kept by Cloudflare under its own retention periods.</li>
        </ul>

        <h2>Your rights</h2>
        <p>You can ask us, by emailing <Mail />, to:</p>
        <ul>
          <li>confirm whether we hold personal information about you and give you a copy (section 23);</li>
          <li>correct or delete information that is inaccurate, out of date, incomplete or misleading (section 24);</li>
          <li>stop processing it, on reasonable grounds relating to your situation (section 11(3)(a)).</li>
        </ul>
        <p>
          We aim to respond within 30 days. If you are unhappy with our response, you can complain to the{" "}
          <a className="underline" href="https://inforegulator.org.za/" rel="noopener noreferrer">
            Information Regulator
          </a>{" "}
          (section 74).
        </p>

        <h2 id="cookies">Cookies</h2>
        <p>
          The site sets no cookies and stores nothing in your browser. There are no analytics, advertising or tracking cookies,
          so there is nothing to opt in to or out of. Our host, Cloudflare, may set short-lived security cookies to filter
          abusive traffic; these are strictly necessary and are not used to identify or follow you.
        </p>

        <h2>Changes</h2>
        <p>We will update this page, and the date at the top, before any change to what we process.</p>
      </Prose>
    </>
  );
}

export function Terms() {
  usePageFocus("terms");
  return (
    <>
      <PageTitle eyebrow={`Last updated ${UPDATED}`}>Terms of use</PageTitle>
      <Prose>
        <h2>What this site is</h2>
        <p>
          The Tender Risk Monitor is a student capstone project by {TEAM} at CTU Training Solutions. It scores South African
          public tender awards against published red-flag rules. It is not an official service of CTU Training Solutions,
          National Treasury or CIPC.
        </p>

        <h2>Scores are not findings</h2>
        <p>
          A risk score and its red flags show patterns in published records that are worth a closer look. They do not show that
          anyone acted unlawfully, and many flagged awards will have ordinary explanations. Do not present a score as proof of
          wrongdoing. Check the source records, and the{" "}
          <a
            className="underline"
            href="https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Rule-Catalogue"
            rel="noopener noreferrer"
          >
            rule catalogue
          </a>{" "}
          that explains each rule, before relying on anything here.
        </p>

        <h2>The data</h2>
        <p>
          Award data comes from National Treasury's eTenders portal through the Open Contracting Data Standard feed, published
          under the Public Domain Dedication and License (PDDL). We show values as published. The feed contains errors, including
          values that appear to be captured in cents, and it does not cover every procurement process: municipalities and
          state-owned entities are included only if they share their data.
        </p>

        <h2>Using the site</h2>
        <ul>
          <li>Do not run automated requests at a rate that degrades the site for others.</li>
          <li>Do not use anything here to harass, threaten or publicly accuse a named person.</li>
        </ul>

        <h2>Corrections</h2>
        <p>
          If you think a record or score is wrong, email <Mail /> with the award reference from the tender page. If the source
          record is wrong, it needs correcting at National Treasury as well; we will reflect corrections when the feed is
          updated.
        </p>

        <h2>No warranty</h2>
        <p>
          The site is provided as is, for research and education, without any promise that it is complete, accurate or
          available. To the extent the law allows, the team is not liable for decisions made using it.
        </p>

        <h2>Source code</h2>
        <p>
          The code is published on{" "}
          <a className="underline" href="https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector" rel="noopener noreferrer">
            GitHub
          </a>{" "}
          under the MIT Licence.
        </p>

        <h2>Law and contact</h2>
        <p>
          These terms are governed by the law of South Africa. Questions go to <Mail />. How we handle personal information is
          set out in the <Link to={href.privacy()} className="underline">privacy notice</Link>.
        </p>
      </Prose>
    </>
  );
}
