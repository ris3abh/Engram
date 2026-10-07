# TeX Live medium plus the packages the paper needs that the medium scheme lacks (all are in arXiv's TeX Live).
FROM texlive/texlive:latest-medium
# Refresh the updater first: a stale tlmgr (the image lags the CTAN tlnet release) makes the
# plain `tlmgr install` below fail with exit 255 on a cross-release mismatch.
RUN tlmgr update --self && tlmgr install placeins inconsolata upquote cleveref xurl && mktexlsr
