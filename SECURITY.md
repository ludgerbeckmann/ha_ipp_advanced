# Security policy

## Supported versions
Only the latest release receives fixes.

## Reporting a vulnerability
Please report a vulnerability privately through GitHub's
[private vulnerability reporting](https://github.com/ludgerbeckmann/ha_ipp_advanced/security/advisories/new)
instead of opening a public issue. Include the version, a short description,
and how to reproduce it. Remove private details from any logs first.

## Scope
IPP Advanced is a custom Home Assistant integration that polls printers over
the local network using the IPP protocol. It stores no data beyond what Home
Assistant itself persists (entity states and history in Home Assistant's own
database) and makes no outbound connections other than to the printer(s) you
configure on your local network.
