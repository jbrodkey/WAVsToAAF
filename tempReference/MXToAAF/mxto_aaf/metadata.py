"""Music-focused metadata extraction for MXToAAF (workspace copy).

Uses mutagen where available and falls back to simple defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

try:
    from mutagen import File as MutagenFile
except Exception:  # pragma: no cover
    MutagenFile = None
    
try:
    import json, subprocess
except Exception:  # pragma: no cover - only used in fallback
    json = None
    subprocess = None


@dataclass
class MusicMetadata:
    path: str
    track_name: Optional[str] = None
    artist: Optional[str] = None
    album_artist: Optional[str] = None
    talent: Optional[str] = None
    composer: Optional[str] = None
    source: Optional[str] = None
    album: Optional[str] = None
    track: Optional[str] = None
    total_tracks: Optional[int] = None
    genre: Optional[str] = None
    catalog_number: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[float] = None
    raw: Dict[str, Any] = None


def extract_music_metadata(path: str) -> MusicMetadata:
    raw = {}
    track_name = artist = album_artist = talent = composer = source = album = track = catalog = description = None
    total_tracks = None
    genre = None
    duration = None

    if MutagenFile is not None:
        try:
            f = MutagenFile(path, easy=True)
            if f is not None:
                # capture raw tags for fallbacks; some filetypes expose keys
                # on different names (mp4 atoms, id3 frames) so keep the raw map
                raw.update({k: v for k, v in f.tags.items()} if getattr(f, "tags", None) else {})
                info = getattr(f, "info", None)
                if info and hasattr(info, "length"):
                    duration = float(info.length)

                def _first(tagname):
                    # Attempt to find a tag by name exactly, or try common
                    # aliases used across formats (ID3, MP4 atom names, etc.)
                    if not getattr(f, "tags", None):
                        return None

                    # direct lookup
                    v = f.tags.get(tagname)
                    if v:
                        return v[0] if isinstance(v, (list, tuple)) else v

                    # aliases we will try
                    aliases = {
                        # title
                        "title": ["\u00a9nam", "TIT2", "TITLE"],
                        # artist / performer
                        "artist": ["\u00a9ART", "TPE1", "performer", "ARTIST", "album_artist"],
                        # composer
                        "composer": ["\u00a9wrt", "TCOM", "COMPOSER"],
                        # album
                        "album": ["\u00a9alb", "TALB", "ALBUM"],
                        # track number
                        "tracknumber": ["trkn", "TRCK", "TRACK", "track", "tracknumber"],
                        # description / comment
                        "comment": ["desc", "COMM", "description", "COMMENT"],
                        # catalog number
                        "catalog": ["catalognumber", "cat", "CATALOGNUMBER", "catalog"],
                    }

                    for key, vals in aliases.items():
                        if tagname == key:
                            for a in vals:
                                if a in f.tags:
                                    vv = f.tags.get(a)
                                    return vv[0] if isinstance(vv, (list, tuple)) else vv

                    return None

                track_name = _first("title")
                artist = _first("artist")
                album_artist = _first("album_artist") or _first("albumartist") or _first("album-artist")
                # talent historically maps to artist; keep explicit 'talent' if present
                talent = _first("talent") or artist or album_artist or _first("authors")
                composer = _first("composer") or _first("COMPOSER")
                album = _first("album")
                # Prefer album or common publisher / label mappings
                source = album or _first("publisher") or _first("label")
                track_field = _first("tracknumber")
                # handle common formats like "6/10" -> track=6, total_tracks=10
                if track_field and isinstance(track_field, str) and "/" in track_field:
                    try:
                        parts = track_field.split("/")
                        track = parts[0].strip()
                        total_tracks = int(parts[1].strip()) if parts[1].strip().isdigit() else None
                    except Exception:
                        # if parsing fails just leave the original
                        track = track_field
                        total_tracks = None
                else:
                    track = track_field
                    total_tracks = None
                # many tags use 'catalog' or 'catalognumber' — also check raw
                description = _first("comment") or _first("description") or _first("notes")
                genre = _first("genre") or _first("GENRE") or _first("music_genre") or _first("style") or _first("contentgroup")
                catalog = _first("catalog") or _first("catalognumber") or _first("CATALOGNUMBER") or None
                # Some tag sets expose keys only in the raw tag dict — attempt
                # to fall back to those values if the normal lookup didn't find them.
                def _raw_first(*keys):
                    for k in keys:
                        v = raw.get(k)
                        if v:
                            return v[0] if isinstance(v, (list, tuple)) else v
                    return None

                artist = artist or _raw_first("artist", "ARTIST", "\u00a9ART")
                album_artist = album_artist or _raw_first("album_artist", "albumartist", "album-artist")
                # If talent is still missing, prefer an explicit 'talent' key, then artist/album_artist
                talent = talent or _raw_first("talent") or artist or album_artist or _raw_first("authors")
        except Exception:
            pass

    # If mutagen didn't provide tags, try ffprobe (ffmpeg suite) as a robust
    # fallback — many systems have ffmpeg/ffprobe available and it understands
    # MP4/M4A atoms. This lets us read Finder-visible tags on macOS MP4 files
    # even when mutagen isn't installed in the Python environment.
    if not raw and json is not None and subprocess is not None:
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_entries", "format_tags", path]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            j = json.loads(proc.stdout)
            tags = j.get("format", {}).get("tags", {}) if isinstance(j, dict) else {}
            # normalize typical tag names (mp4 atoms etc.)
            def _try_tags(keynames):
                for k in keynames:
                    if k in tags and tags[k]:
                        return tags[k]
                return None

            track_name = track_name or _try_tags(["title", "TITLE", "\u00a9nam"]) or _try_tags([k for k in tags.keys() if k.lower().endswith("title")])
            talent = talent or _try_tags(["artist", "ARTIST", "\u00a9ART", "author"])
            composer = composer or _try_tags(["composer", "COMPOSER"])
            album = album or _try_tags(["album", "ALBUM", "\u00a9alb"])
            source = source or album or _try_tags(["publisher", "label"])
            track_field = track or _try_tags(["track", "TRACK", "tracknumber", "trkn", "TRCK"])
            # parse track field for total_tracks if present
            if track_field and isinstance(track_field, str) and "/" in track_field:
                try:
                    parts = track_field.split("/")
                    track = parts[0].strip()
                    if not total_tracks:
                        total_tracks = int(parts[1].strip()) if parts[1].strip().isdigit() else None
                except Exception:
                    track = track_field
            else:
                track = track_field
            
            genre = genre or _try_tags(["genre", "GENRE", "style", "contentgroup"]) 
            catalog = catalog or _try_tags(["catalog", "catalog_number", "catalognumber", "grouping"])
            description = description or _try_tags(["description", "comment", "desc", "COMMENTS", "COMM"]) or _try_tags([k for k in tags.keys() if k.lower().endswith("comment") or k.lower().endswith("description")])
            if not duration:
                dur = _try_tags(["duration", "DURATION"]) or j.get("format", {}).get("duration")
                try:
                    duration = float(dur) if dur is not None else None
                except Exception:
                    duration = None
            # keep tags available for debugging
            raw.update(tags or {})
        except Exception:
            # If ffprobe isn't present or parsing fails, just continue
            pass

    if not track_name:
        import os

        track_name = os.path.splitext(os.path.basename(path))[0]
    # Final fallback: if artist/album_artist are still missing, try raw tag keys
    if not artist:
        artist = raw.get('artist') or raw.get('ARTIST') or raw.get('\u00a9ART')
    if not album_artist:
        album_artist = raw.get('album_artist') or raw.get('albumartist') or raw.get('album-artist')

    # Normalize/clean genre if it is an ID3 numeric code like "(17)" or "17"
    def _normalize_genre(g: Optional[str]) -> Optional[str]:
        if not g:
            return g
        s = str(g).strip()
        # Handle values like "(17)" or "(17) Rock" produced by some taggers
        import re
        m = re.match(r"^\(?\s*(\d{1,3})\s*\)?(?:\s*-?\s*(.*))?$", s)
        if m:
            idx = int(m.group(1))
            remainder = (m.group(2) or '').strip()
            ID3_V1_GENRES = [
                "Blues","Classic Rock","Country","Dance","Disco","Funk","Grunge","Hip-Hop","Jazz","Metal","New Age","Oldies","Other","Pop","R&B","Rap","Reggae","Rock","Techno","Industrial","Alternative","Ska","Death Metal","Pranks","Soundtrack","Euro-Techno","Ambient","Trip-Hop","Vocal","Jazz+Funk","Fusion","Trance","Classical","Instrumental","Acid","House","Game","Sound Clip","Gospel","Noise","AlternRock","Bass","Soul","Punk","Space","Meditative","Instrumental Pop","Instrumental Rock","Ethnic","Gothic","Darkwave","Techno-Industrial","Electronic","Pop-Folk","Eurodance","Dream","Southern Rock","Comedy","Cult","Gangsta","Top 40","Christian Rap","Pop/Funk","Jungle","Native American","Cabaret","New Wave","Psychadelic","Rave","Showtunes","Trailer","Lo-Fi","Tribal","Acid Punk","Acid Jazz","Polka","Retro","Musical","Rock & Roll","Hard Rock",
            ]
            name = ID3_V1_GENRES[idx] if 0 <= idx < len(ID3_V1_GENRES) else None
            # Prefer explicit remainder text if present, else mapped name
            return remainder or name or s
        # Clean common placeholders
        if s.lower() in {"", "unknown", "undef", "genre"}:
            return None
        return s

    genre = _normalize_genre(genre)

    return MusicMetadata(
        path=path,
        track_name=track_name,
        artist=artist,
        album_artist=album_artist,
        talent=talent,
        composer=composer,
        source=source,
        album=album,
        track=track,
        total_tracks=total_tracks,
        genre=genre,
        catalog_number=catalog,
        description=description,
        duration=duration,
        raw=raw,
    )


__all__ = ["extract_music_metadata", "MusicMetadata"]
