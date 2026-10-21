$ErrorActionPreference = 'Stop'

$sourceRoot = 'C:\Users\PatrickFreeland\OneDrive - Affiliated Tribes of Northwest Indians\Pictures'
$siteRoot = 'I:\climate-action-taskforce\site\assets\images'
$reviewAssetRoot = 'I:\climate-action-taskforce\work\review\assets'
$receiptPath = 'I:\climate-action-taskforce\work\review\scene-assets.json'
$selection = @(
    @{ source = 'Images\PNW.jpg'; output = 'scene-forest.jpg' },
    @{ source = 'Images\IMG_7016.jpeg'; output = 'scene-coast.jpg' },
    @{ source = 'Images\airplane-view-islands.jpeg'; output = 'scene-islands.jpg' },
    @{ source = 'Images\IMG_6150.JPG'; output = 'scene-sunset.jpg'; local_only = $true },
    @{ source = 'Images\IMG_4954.jpeg'; output = 'scene-river.jpg' },
    @{ source = 'Images\IMG_3874.jpg'; output = 'scene-aurora.jpg' },
    @{ source = 'fire_lgihting.jpg'; output = 'scene-fire.jpg' },
    @{ source = 'floods.jpg'; output = 'scene-flood.jpg' },
    @{ source = 'hurricane_space.jpg'; output = 'scene-hurricane.jpg' },
    @{ source = 'idalias.jpeg'; output = 'scene-storm.jpg' },
    @{ source = 'tornado.jpg'; output = 'scene-tornado.jpg' }
)

# Inspect metadata without rewriting user photos; reject fields that may identify a person or location.
$inspect = @'
import json, sys
from PIL import Image, ExifTags, IptcImagePlugin

sensitive = {
    'GPSInfo', 'Artist', 'Copyright', 'CameraOwnerName', 'BodySerialNumber',
    'LensSerialNumber', 'ImageUniqueID', 'HostComputer', 'UserComment',
    'XPAuthor', 'XPComment', 'ImageDescription', 'DocumentName'
}
result = []
for path in sys.argv[1:]:
    with Image.open(path) as image:
        if image.format != 'JPEG':
            raise ValueError(f'Expected JPEG: {path}')
        exif = image.getexif()
        fields = {ExifTags.TAGS.get(tag, str(tag)) for tag in exif}
        fields.update(ExifTags.TAGS.get(tag, str(tag)) for tag in exif.get_ifd(ExifTags.IFD.Exif))
        flags = sorted(fields & sensitive)
        if exif.get_ifd(ExifTags.IFD.GPSInfo):
            flags.append('GPS IFD')
        for key in ('xmp', 'photoshop', 'comment'):
            if image.info.get(key):
                flags.append(key)
        attribution = {name: str(exif[tag]) for tag in exif for name in [ExifTags.TAGS.get(tag, str(tag))]
                       if name in ('Artist', 'Copyright', 'ImageDescription')}
        iptc = IptcImagePlugin.getiptcinfo(image) or {}
        iptc_attribution = {name: iptc[tag].decode('utf-8', 'replace') for tag, name in
                            [((2, 80), 'creator'), ((2, 116), 'copyright'), ((2, 120), 'caption'), ((2, 230), 'source_url')]
                            if tag in iptc and isinstance(iptc[tag], bytes)}
        result.append({'width': image.width, 'height': image.height,
                       'private_metadata_flags': sorted(set(flags)),
                       'embedded_attribution': attribution, 'iptc_attribution': iptc_attribution})
print(json.dumps(result))
'@

$sourcePaths = @($selection | ForEach-Object {
    $path = Join-Path $sourceRoot $_.source
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing source: $path" }
    $path
})
$inspectionJson = & py -c $inspect @sourcePaths
$nativeExit = $LASTEXITCODE
if ($nativeExit -ne 0) { throw "Image metadata inspection failed ($nativeExit)" }
$inspection = @($inspectionJson | ConvertFrom-Json)
if ($inspection.Count -ne $selection.Count) { throw 'Image metadata count mismatch' }

$records = for ($i = 0; $i -lt $selection.Count; $i++) {
    $item = $selection[$i]
    $source = $sourcePaths[$i]
    $destination = Join-Path $(if ($item.local_only) { $reviewAssetRoot } else { $siteRoot }) $item.output
    $flags = @($inspection[$i].private_metadata_flags)
    $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    $sourceBytes = (Get-Item -LiteralPath $source).Length
    # This exact fire file's XMP contains editing IDs/tool only; re-review if its bytes change.
    if ($item.output -eq 'scene-fire.jpg' -and $sourceHash -eq '3bb8c63295700addffb20ebecb6a16dad966f12f753f289e382da8f5d7cdfc8e') {
        $flags = @($flags | Where-Object { $_ -ne 'xmp' })
    }
    if ($item.local_only -and (Test-Path -LiteralPath (Join-Path $siteRoot $item.output))) {
        throw "Local-only image remains in site: $($item.output)"
    }
    if ($flags.Count) {
        if (Test-Path -LiteralPath $destination) { throw "Sensitive image already copied: $destination" }
        $status = 'excluded_private_metadata'
    } else {
        if (Test-Path -LiteralPath $destination) {
            $existingHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($existingHash -ne $sourceHash) { throw "Existing asset differs: $destination" }
        } else {
            Copy-Item -LiteralPath $source -Destination $destination
        }
        $copiedHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        $copiedBytes = (Get-Item -LiteralPath $destination).Length
        if ($copiedHash -ne $sourceHash -or $copiedBytes -ne $sourceBytes) { throw "Copy verification failed: $destination" }
        $status = if ($item.local_only) { 'retained_local_byte_identical' } else { 'copied_byte_identical' }
    }
    [pscustomobject]@{
        source_path = $source
        site_path = if ($status -eq 'copied_byte_identical') { $destination } else { $null }
        local_path = if ($status -eq 'retained_local_byte_identical') { $destination } else { $null }
        intended_output = $item.output
        status = $status
        width = $inspection[$i].width
        height = $inspection[$i].height
        bytes = $sourceBytes
        sha256 = $sourceHash
        private_metadata_flags = $flags
        embedded_attribution = $inspection[$i].embedded_attribution
        iptc_attribution = $inspection[$i].iptc_attribution
    }
}

$receipt = [pscustomobject]@{
    purpose = 'Local scene asset copy receipt; source paths and metadata findings are not for site publication.'
    assets = @($records)
    deferred = @(
        'Named tom-barrett Unsplash photo: available, not copied pending source/license clarity.',
        'DUFYDFG.jpg: not copied pending source/license clarity; not found at the named source root.'
    )
    performance_note = 'Unused 12,361,041-byte scene-sunset.jpg is retained in work/review/assets, outside the site.'
}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding utf8
$records | Select-Object intended_output, status, width, height, bytes, sha256, private_metadata_flags | ConvertTo-Json -Depth 4
exit 0
