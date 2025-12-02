"""MXToAAF AAF writer — embed PCM WAV into AAF using aaf2 when available."""
from __future__ import annotations

import json
import os
import wave
import tempfile
import hashlib
from pathlib import Path
from .metadata import MusicMetadata

try:
    import aaf2
    import aaf2.auid
    import aaf2.rational
except Exception:  # pragma: no cover - optional runtime dep
    aaf2 = None

# Standard AAF parameter and operation definitions for pan control
AAF_PARAMETERDEF_PAN = None
AAF_OPERATIONDEF_MONOAUDIOPAN = None
if aaf2:
    try:
        AAF_PARAMETERDEF_PAN = aaf2.auid.AUID("e4962322-2267-11d3-8a4c-0050040ef7d2")
        AAF_OPERATIONDEF_MONOAUDIOPAN = aaf2.auid.AUID("9d2ea893-0968-11d3-8a38-0050040ef7d2")
    except Exception:
        pass


def _apply_pan_to_slot(f, mslot, mclip, pan_value: float, length_val: int):
    """Add pan control to a master timeline slot using OperationGroup with VaryingValue.
    
    Args:
        f: AAF file handle
        mslot: Master timeline slot
        mclip: Source clip to wrap
        pan_value: Pan position (-1.0 = left, 0.0 = center, 1.0 = right)
        length_val: Length in samples/frames
    """
    if AAF_PARAMETERDEF_PAN is None or AAF_OPERATIONDEF_MONOAUDIOPAN is None:
        # Fallback: no pan control, just use the clip directly
        mslot.segment = mclip
        return
    
    try:
        # Register ParameterDef for Pan
        typedef = f.dictionary.lookup_typedef("Rational")
        param_def = f.create.ParameterDef(AAF_PARAMETERDEF_PAN, "Pan", "Pan", typedef)
        try:
            f.dictionary.register_def(param_def)
        except Exception:
            # Already registered
            param_def = f.dictionary.lookup_def(AAF_PARAMETERDEF_PAN)
        
        # Register InterpolationDef
        try:
            interp_def = f.create.InterpolationDef(
                aaf2.misc.LinearInterp, "LinearInterp", "LinearInterp"
            )
            f.dictionary.register_def(interp_def)
        except Exception:
            interp_def = f.dictionary.lookup_def(aaf2.misc.LinearInterp)
        
        # Register OperationDef for MonoAudioPan
        try:
            opdef = f.create.OperationDef(AAF_OPERATIONDEF_MONOAUDIOPAN, "Audio Pan")
            opdef.media_kind = "sound"
            opdef["NumberInputs"].value = 1
            f.dictionary.register_def(opdef)
        except Exception:
            opdef = f.dictionary.lookup_def(AAF_OPERATIONDEF_MONOAUDIOPAN)
        
        # Create OperationGroup to hold the pan operation
        opgroup = f.create.OperationGroup(opdef)
        opgroup.media_kind = "sound"
        opgroup.length = int(length_val)
        
        # Create VaryingValue with constant pan throughout
        # Pan values stored as Rational: -1/1 = left, 0/1 = center, 1/1 = right
        if pan_value == 0.0:
            pan_rational = aaf2.rational.AAFRational("0/1")
        elif pan_value < 0:
            pan_rational = aaf2.rational.AAFRational("-1/1")
        else:
            pan_rational = aaf2.rational.AAFRational("1/1")
        
        c1 = f.create.ControlPoint()
        c1["ControlPointSource"].value = 2
        c1["Time"].value = aaf2.rational.AAFRational(f"0/{int(length_val)}")
        c1["Value"].value = pan_rational
        
        c2 = f.create.ControlPoint()
        c2["ControlPointSource"].value = 2
        c2["Time"].value = aaf2.rational.AAFRational(f"{int(length_val) - 1}/{int(length_val)}")
        c2["Value"].value = pan_rational
        
        varying_value = f.create.VaryingValue()
        varying_value.parameterdef = param_def
        varying_value["Interpolation"].value = interp_def
        varying_value["PointList"].extend([c1, c2])
        
        opgroup.parameters.append(varying_value)
        opgroup.segments.append(mclip)
        
        # Set the OperationGroup as the slot's segment
        mslot.segment = opgroup
    except Exception:
        # Fallback if pan control fails: just use the clip directly
        mslot.segment = mclip


def create_music_aaf(
    wav_path: str,
    metadata: MusicMetadata,
    out_aaf_path: str,
    embed: bool = True,
    tag_map: dict | None = None,
    fps: float = 24.0,
) -> str:
    """Create AAF embedding the provided WAV file and attach metadata.

    Args:
        wav_path: Path to WAV file
        metadata: Extracted music metadata
        out_aaf_path: Output AAF path
        embed: Whether to embed audio essence
        tag_map: Custom metadata field mapping
        fps: Frame rate for AAF timeline (default: 24.0)

    - If embed is False, writes a JSON manifest describing the intended AAF.
    - If embed is True: requires `aaf2` and a valid WAV to import.
    """
    if embed and aaf2 is None:
        raise ImportError("aaf2 required to embed essence into AAFs")

    if not embed:
        # write both original metadata (as extracted) and the AAF tag-mapped
        # representation so callers can verify how fields will appear in AAF.
        aaf_meta = _apply_tag_map(metadata, tag_map)
        manifest = {
            "source": wav_path,
            "aaf": out_aaf_path,
            "metadata": metadata.__dict__,
            "aaf_metadata": aaf_meta,
        }
        with open(out_aaf_path + ".manifest.json", "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        return out_aaf_path + ".manifest.json"

    # embed path
    if not os.path.exists(wav_path):
        raise FileNotFoundError(wav_path)

    # read sample rate from wav header (expected PCM WAV)
    try:
        with wave.open(wav_path, "rb") as wf:
            framerate = wf.getframerate()
    except Exception:
        framerate = None

    # Create an AAF file that mirrors WAVsToAAF structure: MasterMob + SourceMob(s)
    with aaf2.open(out_aaf_path, "w") as f:
        # read raw wav header details
        with wave.open(wav_path, "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            frames = wf.getnframes()

        def _deterministic_mobid(path: str, suffix: str = "master"):
            try:
                abs_path = str(Path(path).resolve())
                stat = Path(path).stat()
                seed = f"{abs_path}|{stat.st_size}|{int(stat.st_mtime)}|{suffix}".encode("utf-8")
                h = hashlib.sha256(seed).digest()[:16]
                parts = [h[i:i+4].hex() for i in range(0, 16, 4)]
                prefix = "060a2b34.01010105.01010f20.13000000"
                urn = f"urn:smpte:umid:{prefix}.{'.'.join(parts)}"
                return aaf2.mobid.MobID(urn)
            except Exception:
                return aaf2.mobid.MobID.new()

        channel_source_mobs = []
        tmp_files = []
        try:
            if channels > 1:
                with wave.open(wav_path, "rb") as r:
                    nframes = r.getnframes()
                    sampwidth = r.getsampwidth()
                    fr = r.getframerate()
                    nch = r.getnchannels()
                    raw = r.readframes(nframes)

                bytes_per_frame = sampwidth * nch
                channel_bytes = [bytearray() for _ in range(nch)]
                for i in range(nframes):
                    off = i * bytes_per_frame
                    for c in range(nch):
                        start = off + c * sampwidth
                        channel_bytes[c].extend(raw[start:start+sampwidth])

                for idx, chdata in enumerate(channel_bytes, start=1):
                    tmp = tempfile.NamedTemporaryFile(prefix=f"mxto_ch{idx}_", suffix=".wav", delete=False)
                    tmp_files.append(tmp.name)
                    tmp.close()
                    with wave.open(tmp.name, "wb") as w:
                        w.setnchannels(1)
                        w.setsampwidth(sampwidth)
                        w.setframerate(fr)
                        w.writeframes(bytes(chdata))

                    src_mob = f.create.SourceMob(Path(tmp.name).stem + ".PHYS")
                    src_mob.import_audio_essence(tmp.name, edit_rate=sample_rate)
                    channel_source_mobs.append(src_mob)
            else:
                src_mob = f.create.SourceMob(Path(wav_path).name + ".PHYS")
                src_mob.import_audio_essence(wav_path, edit_rate=sample_rate)
                channel_source_mobs.append(src_mob)

            master = f.create.MasterMob()
            # Set MasterMob name to Source_TrackName so Avid "Name" column reflects it
            _src_val = getattr(metadata, 'source', None) or getattr(metadata, 'album', None)
            _tn_val = metadata.track_name or Path(wav_path).stem
            _combined_name = f"{_src_val}_{_tn_val}" if _src_val else _tn_val
            master.name = _combined_name
            master.mob_id = _deterministic_mobid(wav_path, "master")

            master_edit_rate = fps
            for i, src_mob in enumerate(channel_source_mobs, start=1):
                src_slot_id = 1
                mslot = master.create_timeline_slot(master_edit_rate)
                mclip = f.create.SourceClip()
                mclip["DataDefinition"].value = f.dictionary.lookup_datadef("sound")
                try:
                    src_slot = list(src_mob.slots)[0]
                    length_val = getattr(src_slot, "length", None) or getattr(src_slot.segment, "length", None) or frames
                except Exception:
                    length_val = frames

                mclip["Length"].value = int(length_val)
                mclip["StartTime"].value = 0
                mclip["SourceID"].value = src_mob.mob_id
                mclip["SourceMobSlotID"].value = src_slot_id
                
                # Apply pan based on channel count
                if len(channel_source_mobs) == 2:
                    # Stereo: channel 1 = left (-1.0), channel 2 = right (1.0)
                    pan_value = -1.0 if i == 1 else 1.0
                    _apply_pan_to_slot(f, mslot, mclip, pan_value, length_val)
                elif len(channel_source_mobs) == 1:
                    # Mono: center pan (0.0)
                    _apply_pan_to_slot(f, mslot, mclip, 0.0, length_val)
                else:
                    # Multi-channel (>2): default to no pan control
                    mslot.segment = mclip
                
                # Set PhysicalTrackNumber for proper channel identification
                try:
                    mslot["PhysicalTrackNumber"].value = i
                except Exception:
                    pass

            aaf_meta = _apply_tag_map(metadata, tag_map)
            for k, v in aaf_meta.items():
                try:
                    master.comments[k] = str(v)
                except Exception:
                    pass

            # Write Avid-friendly field names for key metadata
            try:
                # Track Name (primary title)
                if metadata.track_name:
                    master.comments["Track Name"] = str(metadata.track_name)
                
                # Track (track number only, not "6/10" format)
                if metadata.track:
                    track_val = str(metadata.track).split('/')[0].strip() if '/' in str(metadata.track) else str(metadata.track)
                    master.comments["Track"] = track_val
                
                # Total Tracks
                if metadata.total_tracks is not None:
                    master.comments["Total Tracks"] = str(int(metadata.total_tracks))
                
                # Genre
                if metadata.genre:
                    master.comments["Genre"] = str(metadata.genre)
            except Exception:
                pass

            # ensure Description plus a set of Avid-friendly keys are present
            try:
                if metadata.description:
                    master.comments["Description"] = str(metadata.description)

                # Friendly name: Source_TrackName (e.g., Flicka_Herd Overlook)
                src_val = getattr(metadata, 'source', None) or getattr(metadata, 'album', None)
                tn_val = metadata.track_name or Path(wav_path).stem
                combined_name = f"{src_val}_{tn_val}" if src_val else tn_val
                master.comments["Name"] = str(combined_name)
                master.comments["Filename"] = str(Path(wav_path).name)
                master.comments["FilePath"] = str(Path(wav_path))

                # audio properties
                try:
                    master.comments["SampleRate"] = str(int(sample_rate))
                    # we can compute bit depth if a source frame size is available
                    # but we don't have sampwidth here for the split case; default to empty
                    try:
                        with wave.open(wav_path, 'rb') as _w:
                            master.comments["BitDepth"] = str(_w.getsampwidth() * 8)
                    except Exception:
                        pass
                    master.comments["Channels"] = str(len(channel_source_mobs))
                    master.comments["Number of Frames"] = str(int(frames))
                except Exception:
                    pass

                tracks_label = 'A1' if len(channel_source_mobs) == 1 else ('A1A2' if len(channel_source_mobs) == 2 else f"A1A{len(channel_source_mobs)}")
                master.comments['Tracks'] = tracks_label

                # Duration (seconds) — prefer metadata.duration if present
                if metadata.duration:
                    master.comments['Duration'] = f"{float(metadata.duration):.3f}"
                else:
                    master.comments['Duration'] = str(int(frames))

                # If metadata provides total_tracks or genre, write those too
                try:
                    if getattr(metadata, 'total_tracks', None) is not None:
                        master.comments['TotalTracks'] = str(int(metadata.total_tracks))
                except Exception:
                    pass

                try:
                    if getattr(metadata, 'genre', None):
                        master.comments['Genre'] = str(metadata.genre)
                except Exception:
                    pass

                # Artist & Talent handling: write both Artist and Talent.
                # If both artist and album_artist are present and different,
                # preserve both separately. Otherwise, set both to the same value
                try:
                    artist_val = getattr(metadata, 'artist', None)
                    album_artist_val = getattr(metadata, 'album_artist', None)
                    talent_val = getattr(metadata, 'talent', None)

                    # Decide values
                    if artist_val and album_artist_val and artist_val != album_artist_val:
                        master.comments['Artist'] = str(artist_val)
                        master.comments['Talent'] = str(album_artist_val)
                    else:
                        # prefer explicit talent field, then artist, then album_artist
                        chosen = talent_val or artist_val or album_artist_val
                        if chosen:
                            master.comments['Artist'] = str(chosen)
                            master.comments['Talent'] = str(chosen)
                except Exception:
                    pass
            except Exception:
                # Don't fail the whole write if comments fail
                pass

            f.content.mobs.append(master)
            for src in channel_source_mobs:
                f.content.mobs.append(src)
        finally:
            for p in tmp_files:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    return out_aaf_path


def _apply_tag_map(metadata: MusicMetadata, tag_map: dict | None) -> dict:
    """Return a mapping of AAF tag name -> metadata value.

    `tag_map` maps metadata field names (e.g. 'track_name') to target AAF
    tag name (e.g. 'TrackName' or 'Avid:Title'). If tag_map is None, a
    conservative default mapping is used.
    """
    defaults = {
        "track_name": "TrackName",
        "talent": "Artist",
        "composer": "Composer",
        "album": "Album",
        "source": "Source",
        "track": "TrackNumber",
        "total_tracks": "TotalTracks",
        "genre": "Genre",
        "catalog_number": "CatalogNumber",
        "description": "Description",
        "duration": "Duration",
    }
    mapping = (tag_map or defaults) if tag_map is not None else defaults

    out = {}
    for field, dest in mapping.items():
        val = getattr(metadata, field, None)
        if val is not None:
            out[dest] = val
    return out


__all__ = ["create_music_aaf"]
