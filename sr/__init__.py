"""SR Generator - private AI band music workstation.

Stage 7: Band-specific music generation. A band adapter is distilled from the
approved Band DNA (character / tempo / key priors); the music provider renders a
deterministic instrumental bed for a section, tempo-locked to the song, that band
vocals then render over. The synth engine is a stand-in for a real generative
model - swap SR_MUSIC_PROVIDER=http to point at one. See ROADMAP.md.
"""

__version__ = "0.7.0"
