"use client";

import Link from "next/link";

export default function HelpPage() {
  return (
    <div className="help">
      <h1>How it works</h1>
      <p className="muted">
        SR Generator builds a full, editable song from your band. You bring the
        band (real voices, real players, or ready-made styles); it writes and
        performs the track, and every part stays editable afterwards.
      </p>

      <ol className="help-steps">
        <li>
          <h3>1 · Make a band</h3>
          <p>
            Go to <Link href="/band">Band</Link>. Your band has a name (edit it at
            the top) and keeps its own singers, players and songs. Need a second
            band with a different line-up? Hit <b>+ new band</b> — switch between
            them any time. Everything saves as you go.
          </p>
        </li>

        <li>
          <h3>2 · Add vocalists</h3>
          <p>
            Under <b>Vocalists</b>, add a singer and either <b>record</b> straight
            from your mic or <b>upload</b> a few clips (10–30s of clear singing).
            Hit <b>Train voice</b>. Tick <b>generation OK</b> so they can be used.
            You can also tune pitch / brightness / rasp by hand.
          </p>
        </li>

        <li>
          <h3>3 · Add players</h3>
          <p>
            Under <b>Players</b> you have three ways to fill each instrument
            (lead / rhythm guitar, bass, drums, keys):
          </p>
          <ul>
            <li>
              <b>Signature styles</b> — one click for a ready-made playing style,
              acoustic through modern metal, for any instrument. Tweak it after.
            </li>
            <li>
              <b>Learn from songs</b> — upload tracks a player performed on (or a
              Google Drive folder link). Their instrument is separated out and
              their style is learned: drive, tone, timing feel, how busy, how
              dynamic. First training installs the separation engine (one time).
            </li>
            <li>
              <b>By hand</b> — add a player and set the style sliders yourself.
            </li>
          </ul>
          <p>Tick <b>generation OK</b> for anyone you want to use.</p>
        </li>

        <li>
          <h3>4 · Start a song</h3>
          <p>
            From <Link href="/">Home</Link>, give the song a title and pick a{" "}
            <b>genre / feel</b> (metal, sludge, doom, punk, acoustic, folk,
            synthwave…). The <b>blend slider</b> sets how far the band bends toward
            that genre: 0% plays like your band, 100% goes fully into the style.
            Add a sentence about the mood if you like.
          </p>
        </li>

        <li>
          <h3>5 · Lyrics (optional)</h3>
          <p>
            On the <b>Story</b> step, type lyrics — one line per row — or leave it
            blank. If blank, a placeholder scaffold fills in so you can hear the
            structure; come back and rewrite it, then regenerate.
          </p>
        </li>

        <li>
          <h3>6 · Cast the band</h3>
          <p>
            On the <b>Cast</b> step, hit <b>Cast the whole band</b> — it puts each
            member on their part and arranges the singers. Or set each instrument
            yourself from its dropdown. Open <b>tweak</b> on any instrument for the
            dials (sparser↔busier, darker↔brighter, softer↔harder, laid-back↔pushed,
            straight↔swung) and the <b>explore</b> knob — 0 stays true to the
            learned style, higher lets them try new things.
          </p>
        </li>

        <li>
          <h3>7 · Generate & edit</h3>
          <p>
            Hit <b>Generate song</b>. On the <b>Studio</b> step you get the full
            mix, a master, and every instrument and vocal as its own stem. Open a
            section to regenerate just that part, swap a player or singer for one
            section, lock a section you like, or roll back — the rest of the song
            stays exactly as it was.
          </p>
        </li>
      </ol>

      <h2>Good to know</h2>
      <ul>
        <li>
          <b>Nothing generates without consent.</b> Each singer and player has a
          “generation OK” toggle; it&apos;s off until you set it.
        </li>
        <li>
          <b>It&apos;s deterministic.</b> The same song, seed and settings always
          produce the same audio — so a small tweak changes only what you touched.
        </li>
        <li>
          <b>Band DNA</b> (separate page) is optional: point it at a folder or
          Drive link of your catalogue to learn the band&apos;s overall sound and
          feed it into generation.
        </li>
        <li>
          Signature styles and genres are <b>style archetypes</b>, not anyone&apos;s
          recordings.
        </li>
      </ul>
    </div>
  );
}
