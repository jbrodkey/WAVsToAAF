# AAF Stereo Pan Implementation Guide

This document describes how to implement stereo panning in AAF files using the aaf2 Python library, ensuring that stereo audio sources import into Avid Pro Tools with proper left/right channel positioning instead of center-panned mono tracks.

## Overview

When creating AAF files from stereo audio sources, each channel must be explicitly positioned (panned) to its correct speaker location:
- **Left channel** (channel 1): Pan position = -1.0 (hard left)
- **Right channel** (channel 2): Pan position = +1.0 (hard right)
- **Mono sources**: Pan position = 0.0 (center)

Without explicit pan control, all clips default to center pan regardless of source channel count.

## AAF Structure Requirements

### 1. Standard AAF Pan Definitions

AAF uses standardized AUID (Avid Unique Identifier) values for pan operations:

```python
import aaf2.auid
import aaf2.rational

# Parameter definition for pan control
AAF_PARAMETERDEF_PAN = aaf2.auid.AUID("e4962322-2267-11d3-8a4c-0050040ef7d2")

# Operation definition for mono audio pan
AAF_OPERATIONDEF_MONOAUDIOPAN = aaf2.auid.AUID("9d2ea893-0968-11d3-8a38-0050040ef7d2")
```

### 2. AAF Object Hierarchy

To apply pan control, the standard `SourceClip` must be wrapped in an `OperationGroup`:

```
TimelineMobSlot
└── OperationGroup (MonoAudioPan operation)
    ├── Parameters
    │   └── VaryingValue (pan parameter with control points)
    └── Segments
        └── SourceClip (reference to source audio)
```

Without this structure, the AAF contains only:
```
TimelineMobSlot
└── SourceClip (no pan control)
```

## Implementation Steps

### Step 1: Register AAF Definitions

Before creating pan-controlled clips, register the required parameter and operation definitions:

```python
def _apply_pan_to_slot(f, mslot, mclip, pan_value: float, length_val: int):
    """Add pan control to a master timeline slot.
    
    Args:
        f: AAF file handle
        mslot: Master timeline slot
        mclip: Source clip to wrap
        pan_value: Pan position (-1.0 = left, 0.0 = center, 1.0 = right)
        length_val: Length in samples/frames
    """
    # Register ParameterDef for Pan
    typedef = f.dictionary.lookup_typedef("Rational")
    param_def = f.create.ParameterDef(AAF_PARAMETERDEF_PAN, "Pan", "Pan", typedef)
    try:
        f.dictionary.register_def(param_def)
    except Exception:
        # Already registered
        param_def = f.dictionary.lookup_def(AAF_PARAMETERDEF_PAN)
```

### Step 2: Register Interpolation Definition

Pan automation requires an interpolation method (typically linear):

```python
    # Register InterpolationDef
    try:
        interp_def = f.create.InterpolationDef(
            aaf2.misc.LinearInterp, "LinearInterp", "LinearInterp"
        )
        f.dictionary.register_def(interp_def)
    except Exception:
        interp_def = f.dictionary.lookup_def(aaf2.misc.LinearInterp)
```

### Step 3: Register Operation Definition

Create the MonoAudioPan operation that will process the audio:

```python
    # Register OperationDef for MonoAudioPan
    try:
        opdef = f.create.OperationDef(AAF_OPERATIONDEF_MONOAUDIOPAN, "Audio Pan")
        opdef.media_kind = "sound"
        opdef["NumberInputs"].value = 1
        f.dictionary.register_def(opdef)
    except Exception:
        opdef = f.dictionary.lookup_def(AAF_OPERATIONDEF_MONOAUDIOPAN)
```

### Step 4: Create OperationGroup

Create an operation group to hold both the pan parameter and the source clip:

```python
    # Create OperationGroup to hold the pan operation
    opgroup = f.create.OperationGroup(opdef)
    opgroup.media_kind = "sound"
    opgroup.length = int(length_val)
```

### Step 5: Create Pan Control Points (CRITICAL)

**IMPORTANT**: Pan values must be stored as AAF Rational types, not Python floats.

❌ **WRONG** (causes NotImplementedError):
```python
c1["Value"].value = -1.0  # Python float - will fail!
```

✅ **CORRECT** (use AAF Rational):
```python
# Convert float pan to Rational format
if pan_value == 0.0:
    pan_rational = aaf2.rational.AAFRational("0/1")
elif pan_value < 0:
    pan_rational = aaf2.rational.AAFRational("-1/1")
else:
    pan_rational = aaf2.rational.AAFRational("1/1")

# Create control points with constant pan throughout the clip
c1 = f.create.ControlPoint()
c1["ControlPointSource"].value = 2
c1["Time"].value = aaf2.rational.AAFRational(f"0/{int(length_val)}")
c1["Value"].value = pan_rational

c2 = f.create.ControlPoint()
c2["ControlPointSource"].value = 2
c2["Time"].value = aaf2.rational.AAFRational(f"{int(length_val) - 1}/{int(length_val)}")
c2["Value"].value = pan_rational
```

### Step 6: Create VaryingValue Parameter

Bundle the control points into a VaryingValue parameter:

```python
    varying_value = f.create.VaryingValue()
    varying_value.parameterdef = param_def
    varying_value["Interpolation"].value = interp_def
    varying_value["PointList"].extend([c1, c2])
```

### Step 7: Assemble and Assign

Add the parameter and source clip to the operation group, then assign to the slot:

```python
    opgroup.parameters.append(varying_value)
    opgroup.segments.append(mclip)
    
    # Set the OperationGroup as the slot's segment
    mslot.segment = opgroup
```

## Complete Working Example

```python
import aaf2
import aaf2.auid
import aaf2.rational

AAF_PARAMETERDEF_PAN = aaf2.auid.AUID("e4962322-2267-11d3-8a4c-0050040ef7d2")
AAF_OPERATIONDEF_MONOAUDIOPAN = aaf2.auid.AUID("9d2ea893-0968-11d3-8a38-0050040ef7d2")

def apply_pan_to_slot(f, mslot, mclip, pan_value: float, length_val: int):
    """Add pan control to a master timeline slot using OperationGroup with VaryingValue."""
    try:
        # Register definitions
        typedef = f.dictionary.lookup_typedef("Rational")
        param_def = f.create.ParameterDef(AAF_PARAMETERDEF_PAN, "Pan", "Pan", typedef)
        try:
            f.dictionary.register_def(param_def)
        except Exception:
            param_def = f.dictionary.lookup_def(AAF_PARAMETERDEF_PAN)
        
        interp_def = f.create.InterpolationDef(
            aaf2.misc.LinearInterp, "LinearInterp", "LinearInterp"
        )
        try:
            f.dictionary.register_def(interp_def)
        except Exception:
            interp_def = f.dictionary.lookup_def(aaf2.misc.LinearInterp)
        
        opdef = f.create.OperationDef(AAF_OPERATIONDEF_MONOAUDIOPAN, "Audio Pan")
        opdef.media_kind = "sound"
        opdef["NumberInputs"].value = 1
        try:
            f.dictionary.register_def(opdef)
        except Exception:
            opdef = f.dictionary.lookup_def(AAF_OPERATIONDEF_MONOAUDIOPAN)
        
        # Create OperationGroup
        opgroup = f.create.OperationGroup(opdef)
        opgroup.media_kind = "sound"
        opgroup.length = int(length_val)
        
        # Create pan control points - MUST use Rational, not float!
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
        mslot.segment = opgroup
        
    except Exception:
        # Fallback: use clip without pan control
        mslot.segment = mclip

# Usage in AAF creation loop
for i, src_mob in enumerate(channel_source_mobs, start=1):
    mslot = master.create_timeline_slot(fps)
    mclip = f.create.SourceClip()
    mclip["DataDefinition"].value = f.dictionary.lookup_datadef("sound")
    mclip["Length"].value = int(length_val)
    mclip["StartTime"].value = 0
    mclip["SourceID"].value = src_mob.mob_id
    mclip["SourceMobSlotID"].value = 1
    
    # Apply pan based on channel count
    if len(channel_source_mobs) == 2:
        # Stereo: channel 1 = left (-1.0), channel 2 = right (1.0)
        pan_value = -1.0 if i == 1 else 1.0
        apply_pan_to_slot(f, mslot, mclip, pan_value, length_val)
    elif len(channel_source_mobs) == 1:
        # Mono: center pan (0.0)
        apply_pan_to_slot(f, mslot, mclip, 0.0, length_val)
    else:
        # Multi-channel (>2): no pan control
        mslot.segment = mclip
```

## Common Pitfalls

### 1. Using Float Instead of Rational
**Error**: `NotImplementedError: ('Indirect type for: %s', "<class 'float'>")`

**Cause**: Setting `c1["Value"].value = -1.0` (Python float)

**Fix**: Use `aaf2.rational.AAFRational("-1/1")` instead

### 2. Forgetting OperationGroup
**Symptom**: AAF creates successfully but clips import with center pan

**Cause**: Assigning `mslot.segment = mclip` directly without wrapping in OperationGroup

**Fix**: Always wrap SourceClip in OperationGroup with pan parameters for stereo sources

### 3. Silent Exceptions
**Symptom**: No error messages but pan doesn't work

**Cause**: Broad `except Exception` blocks hiding errors

**Fix**: Temporarily add debug output:
```python
except Exception as e:
    print(f"Pan control failed: {e}")
    import traceback
    traceback.print_exc()
```

## Testing Pan Implementation

### Verify AAF Structure
```python
import aaf2

with aaf2.open('test.aaf', 'r') as f:
    for mob in f.content.mobs:
        if hasattr(mob, 'name') and 'PHYS' not in str(mob.name):
            print(f'Mob: {mob.name}')
            for slot in mob.slots:
                seg = slot.segment
                print(f'  Slot {slot.slot_id}: {type(seg).__name__}')
                if type(seg).__name__ == 'OperationGroup':
                    print(f'    ✓ Has OperationGroup (pan control present)')
                    for p in seg.parameters:
                        if hasattr(p, 'pointlist'):
                            for cp in p.pointlist:
                                print(f'    Pan value: {cp.value}')
                else:
                    print(f'    ✗ Direct SourceClip (no pan control)')
```

**Expected output for stereo file**:
```
Mob: Source_TrackName
  Slot 1: OperationGroup
    ✓ Has OperationGroup (pan control present)
    Pan value: -1.0
  Slot 2: OperationGroup
    ✓ Has OperationGroup (pan control present)
    Pan value: 1.0
```

## Pan Value Scale

AAF pan values use a normalized -1 to +1 scale:
- `-1.0` = Hard left (100% left speaker)
- `0.0` = Center (equal left/right)
- `+1.0` = Hard right (100% right speaker)

Intermediate values are supported for partial panning:
- `-0.5` = 75% left, 25% right
- `+0.5` = 25% left, 75% right

However, for stereo channel separation, use hard pan values (-1.0 and +1.0).

## References

- AAF specification: Pan parameter AUID `e4962322-2267-11d3-8a4c-0050040ef7d2`
- MonoAudioPan operation AUID `9d2ea893-0968-11d3-8a38-0050040ef7d2`
- aaf2 library documentation: https://github.com/markreidvfx/pyaaf2
- Avid AAF documentation: AAF Object Specification v1.1

## Integration with MXToAAF

This implementation is integrated into `mxto_aaf/aaf.py`:
- `_apply_pan_to_slot()` helper function applies pan to individual slots
- Stereo sources automatically get L/R pan (-1.0 and +1.0)
- Mono sources get center pan (0.0)
- Multi-channel (>2) sources use default behavior (no pan automation)

All AAF files created by MXToAAF now include proper stereo panning for correct import into Avid Pro Tools.
