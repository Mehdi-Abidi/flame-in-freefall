import Link from "next/link";

const TEAM = ["Mehdi Abidi", "Syed Mufeed Haider", "Moiz Ul Haq", "Ali Soban", "Ahsan Ali", "Syed Taha Zaidi"];

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-rule">
      <div className="mx-auto grid max-w-[1240px] gap-8 px-4 py-10 text-[13px] text-ink-2 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <p className="eyebrow mb-3">Data</p>
          <p className="max-w-md leading-relaxed">
            All measurements come from NASA&apos;s Physical Sciences Informatics repository. Raw videos and sensor files stay on NASA&apos;s
            servers and are linked from each investigation. Photographs are NASA&apos;s, from the NASA Image and Video Library. This project is not endorsed by NASA.
          </p>
        </div>
        <div>
          <p className="eyebrow mb-3">Team</p>
          <ul className="space-y-1">
            {TEAM.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="eyebrow mb-3">Links</p>
          <ul className="space-y-1">
            <li>
              <Link className="link-underline" href="/earth/">
                Back on Earth
              </Link>
            </li>
            <li>
              <Link className="link-underline" href="/method/">
                Method
              </Link>
            </li>
            <li>
              <a className="link-underline" href="https://github.com/Mehdi-Abidi/flame-in-freefall">Source on GitHub</a>
            </li>
            <li>
              <a className="link-underline" href="https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/">The challenge</a>
            </li>
            <li>
              <a className="link-underline" href="https://psi.nasa.gov/physci/repo/search?data_source=psi&data_type=investigation">NASA PSI repository</a>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
