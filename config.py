#!/bin/python

import yaml
import git
import os
import shutil
import time

g_config = None
g_private_repo = 'private'
g_config_filename = 'config.yaml'

def init():
    filepath = g_private_repo + '/' + g_config_filename
    assert not g_config, "config is already loaded"
    assert not os.path.isfile(filepath), filepath + " already exists"

    git.Repo.init(g_private_repo, bare=False)

    shutil.copyfile('config.yaml.example', filepath)
    get()
    commit('Initial commit')

def get():
    global g_config

    if g_config == None:
        filepath = g_private_repo + '/' + g_config_filename
        assert os.path.isfile(filepath), filepath + " does not exist"

        # Make sure all changes in the 'private' repo are committed
        with git.Repo(g_private_repo) as repo:
            is_tree_clean = repo.git.status() == 'On branch master\nnothing to commit, working tree clean'
            assert is_tree_clean, "private tree is not clean"

        with open(filepath) as f:
            g_config = yaml.safe_load(f)

    return g_config

def commit(msg):
    filepath = g_private_repo + '/' + g_config_filename

    with open(filepath, 'w') as f:
        yaml.dump(g_config, f, default_flow_style=False)

    with git.Repo(g_private_repo) as repo:
        repo.git.add(g_config_filename)
        repo.git.commit(m=msg)

