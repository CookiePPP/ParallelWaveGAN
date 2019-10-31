#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Decode with trained Parallel WaveGAN Generator."""

import argparse
import logging
import os

import numpy as np
import soundfile as sf
import torch
import yaml

from tqdm import tqdm

from parallel_wavegan.datasets import MelDataset
from parallel_wavegan.models import ParallelWaveGANGenerator


def main():
    """Run decoding process."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dumpdir", default=None, type=str,
                        help="Directory including feature files.")
    parser.add_argument("--outdir", default=None, type=str,
                        help="Direcotry to save generated speech.")
    parser.add_argument("--checkpoint", default=None, type=str,
                        help="Checkpoint file.")
    parser.add_argument("--config", default=None, type=str,
                        help="Yaml format configuration file.")
    parser.add_argument("--verbose", type=int, default=1,
                        help="logging level (higher is more logging)")
    args = parser.parse_args()

    # set logger
    if args.verbose > 1:
        logging.basicConfig(
            level=logging.DEBUG, format="%(asctime)s (%(module)s:%(lineno)d) %(levelname)s: %(message)s")
    elif args.verbose > 0:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s (%(module)s:%(lineno)d) %(levelname)s: %(message)s")
    else:
        logging.basicConfig(
            level=logging.WARN, format="%(asctime)s (%(module)s:%(lineno)d) %(levelname)s: %(message)s")
        logging.warning('skip DEBUG/INFO messages')

    # check direcotry existence
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)

    # load config
    if args.config is None:
        dirname = os.path.dirname(args.checkpoint)
        args.config = os.path.join(dirname, "config.yml")
    with open(args.config) as f:
        config = yaml.load(f, Loader=yaml.Loader)
    config.update(vars(args))

    # get dataset
    dataset = MelDataset(args.dumpdir)

    # setup
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    model = ParallelWaveGANGenerator(**config["generator_params"])
    model.load_state_dict(torch.load(args.checkpoint, map_location="cpu")["model"]["generator"])
    model.remove_weight_norm()
    model = model.to(device)

    # generate
    pad_size = (config["generator_params"]["aux_context_window"],
                config["generator_params"]["aux_context_window"])
    for feat_path, c in tqdm(dataset):
        z = torch.randn(1, 1, c.shape[0] * config["hop_size"]).to(device)
        c = np.pad(c, (pad_size, (0, 0)), "edge")
        c = torch.FloatTensor(c).unsqueeze(0).transpose(2, 1).to(device)
        with torch.no_grad():
            y = model(z, c)
        write_path = os.path.join(config["outdir"], os.path.basename(feat_path).replace(".npy", "_gen.wav"))
        sf.write(write_path, y.view(-1).cpu().numpy(), config["sampling_rate"], "PCM_16")


if __name__ == "__main__":
    main()