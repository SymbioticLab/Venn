from setuptools import setup, find_packages

setup(
    name='venn',
    version='0.1',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'numpy',
        'pandas',
        'matplotlib'
    ],
    entry_points={
        'console_scripts': [
            'venn=venn:main',
        ],
    },
)