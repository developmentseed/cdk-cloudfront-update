"""cdk-cloudfront-update: """

from setuptools import find_namespace_packages, setup

with open("README.md") as f:
    desc = f.read()

with open("VERSION") as version_file:
    version = version_file.read().strip()

install_requires = [
    "aws-cdk-lib>=2.0.0",
    "constructs>=10.0.0",
    "docker>=6.0.1",
]

extra_reqs = {
    "dev": ["black==22.3.0", "flake8==4.0.1", "pyright==1.1.251", "boto3>=1.26.106"],
}


setup(
    name="cdk-cloudfront-update",
    description=(
        "A CDK construct for adding behaviors and origins"
        "to existing Cloudfront Distributions"
    ),
    long_description=desc,
    long_description_content_type="text/markdown",
    python_requires=">=3.8",
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3.8",
    ],
    keywords="CDK Construct Cloudfront Distribution Behavior Origin",
    maintainer="Edward Keeble",
    maintainer_email="edward@developmentseed.org",
    url="https://github.com/developmentseed/cdk-cloudfront-update",
    license="MIT",
    packages=find_namespace_packages(
        exclude=[
            "tests",
        ]
    ),
    data_files=[("version", ["VERSION"])],
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
    tests_require=extra_reqs["dev"],
    extras_require=extra_reqs,
    version=version,
)
