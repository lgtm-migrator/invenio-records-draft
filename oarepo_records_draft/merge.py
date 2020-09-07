from deepmerge import Merger


def list_merge(config, path, base, nxt):
    for k in range(0, min(len(base), len(nxt))):
        if isinstance(base[k], (dict, list, tuple)):
            draft_merger.merge(base[k], nxt[k])
        else:
            base[k] = nxt[k]
    for k in range(len(base), len(nxt)):
        base.append(nxt[k])
    return base


draft_merger = Merger(
    [
        (list, [list_merge]),
        (dict, ["merge"])
    ],
    ["override"],
    ["override"]
)
