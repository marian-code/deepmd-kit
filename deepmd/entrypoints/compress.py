"""Compress a model, which including tabulating the embedding-net."""

import copy
import json
import logging
from typing import TYPE_CHECKING, Optional

from deepmd.common import j_loader
from deepmd.utils.argcheck import normalize
from deepmd.utils.compat import convert_input_v0_v1

from .freeze import freeze
from .train import train
from .transform import transform

if TYPE_CHECKING:
    try:
        from typing import Protocol  # python >=3.8
    except ImportError:
        from typing_extensions import Protocol  # type: ignore

    class ArgsProto(Protocol):
        """Prococol mimicking parser object."""

        INPUT: str
        input: str
        output: str
        extrapolate: str
        stride: float
        frequency: str
        checkpoint_folder: str
        init_model: Optional[str]
        restart: Optional[str]
        nodes: Optional[str]
        old_model: str
        raw_model: str

__all__ = ["compress"]

log = logging.getLogger(__name__)


def compress(args: "ArgsProto"):
    """Compress model.

    The table is composed of fifth-order polynomial coefficients and is assembled from
    two sub-tables. The first table takes the stride(parameter) as it's uniform stride,
    while the second table takes 10 * stride as it's uniform stride. The range of the
    first table is automatically detected by deepmd-kit, while the second table ranges
    from the first table's upper boundary(upper) to the extrapolate(parameter) * upper.

    Parameters
    ----------
    args : ArgsProto
        arguments object
    """
    jdata = j_loader(args.INPUT)
    if "model" not in jdata.keys():
        jdata = convert_input_v0_v1(jdata, warning=True, dump="input_v1_compat.json")
    jdata = normalize(jdata)
    jdata["model"]["compress"] = {}
    jdata["model"]["compress"]["compress"] = True
    jdata["model"]["compress"]["model_file"] = args.input
    jdata["model"]["compress"]["table_config"] = [
        args.extrapolate,
        args.stride,
        10 * args.stride,
        int(args.frequency),
    ]

    # check the descriptor info of the input file
    assert (
        jdata["model"]["descriptor"]["type"] == "se_a"
    ), "Model compression error: descriptor type must be se_a!"
    assert (
        jdata["model"]["descriptor"]["resnet_dt"] is False
    ), "Model compression error: descriptor resnet_dt must be false!"

    # stage 1: training or refining the model with tabulation
    log.info("\n\n")
    log.info("stage 1: train or refine the model with tabulation")
    args_train = copy.deepcopy(args)
    args_train.INPUT = "compress.json"
    args_train.output = "compress.json"
    args_train.init_model = None
    args_train.restart = None
    jdata["training"]["stop_batch"] = jdata["training"][
        "save_freq"
    ]  # be careful here, if one want to refine the model
    with open(args_train.INPUT, "w") as fp:
        json.dump(jdata, fp, indent=4)
    train(args_train)

    # stage 2: freeze the model
    log.info("\n\n")
    log.info("stage 2: freeze the model")
    args_frz = copy.deepcopy(args)
    args_frz.nodes = None
    freeze(args_frz)

    # stage 3: transform the model
    log.info("\n\n")
    log.info("stage 3: transform the model")
    args_transform = copy.deepcopy(args)
    args_transform.old_model = args.input
    args_transform.raw_model = args.output
    args_transform.output = args.output
    transform(args_transform)