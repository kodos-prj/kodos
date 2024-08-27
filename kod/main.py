from invoke import Collection, Program
from kod import commands

program = Program(namespace=Collection.from_module(commands), version='0.1.0')
