# OpenShift4-tools

[Robert Krawitz's](mailto:rlk@redhat.com) tools for installing
etc. OpenShift 4 clusters.

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-generate-toc again -->
**Table of Contents**

- [OpenShift4-tools](#openshift4-tools)
    - [Cluster utilities](#cluster-utilities)
    - [Testing tools](#testing-tools)
    - [Data reporting utilities](#data-reporting-utilities)
    - [General information tools](#general-information-tools)
    - [PBench orchestration](#pbench-orchestration)
    - [oinst API](#oinst-api)
        - [Introduction](#introduction)
        - [API calls](#api-calls)
        - [Validating Instance Types](#validating-instance-types)

<!-- markdown-toc end -->

## Cluster utilities

- **oinst**: OpenShift 4.x IPI installer wrapper, currently for AWS, GCE,
  and libvirt.

  You may want to install kubechart
  (github.com/sjenning/kubechart/kubechart) and oschart
  (github.com/sjenning/oschart/oschart) to monitor the cluster as it
  boots and runs.

  I welcome PRs to extend this to other platforms.  See [the `oinst`
  API](#oinst-api) below for more information.

- **ocp4-upi-util**: OpenShift 4.x UPI installer wrapper, currently for
  baremetal hosts supporting IPMI.  Needs more documentation.
  Examples in `examples/ocp4-upi-util`.

- **waitfor-pod**: wait for a specified pod to make its appearance (used
  as a helper by `oinst`).

- **bastion-ssh** and **bastion-scp** -- use an ssh bastion to access
   cluster nodes.

- **install-custom-kubelet** -- install a custom kubelet into a cluster.

- **set-worker-parameters** -- set various kubelet parameters and wait
  for the operation to complete

- **clean-cluster**: clean up a libvirt cluster if
  `openshift-install destroy cluster` doesn't work.

- **get-first-master**: find the external IP address first master node of
  a cluster.

- **get-masters**: get the external IP addresses of all of the master
  nodes of a cluster.

- **get-nodes**: get the external (if available) or internal IP address
  of each node in a cluster.

## Testing tools

- **clusterbuster** -- generate pods, namespaces, and secrets to stress
  test a cluster.  See [documentation](docs/clusterbuster.md)

- **force-pull-clusterbuster-image** - force-pull the ClusterBuster
  images so that they are present on all nodes in a cluster.

## Data reporting utilities

- **monitor-cluster-resources** -- monitor CPU, memory, and pod
  utilization per-node in real time.
  
- **net-traffic** -- report information about network traffic similar
  to iostat.

- **prom-extract**: Capture selected Prometheus data for the duration
  of a run; report the results along with metadata and workload output
  JSON-formatted.

  `prom-extract` is written in Python.  It requires the following
  Python3 libraries to be installed:

  - **python3-pyyaml**: available via dnf/yum on Fedora, RHEL, etc.

  - **prometheus-api-client**: not currently packaged.  This can be
    installed via `pip3 install prometheus-api-client`.  *Note that
    this is **not** the same package as `prometheus-client`, which is
    available via dnf*.  `prometheus-api-client` provides the
    Prometheus query API, while `prometheus-client` is a Prometheus
    provider.

	Newer versions of `prometheus-api-client` may require versions of
    `pandas` newer than you can run.  If so, you will need to install
    `prometheus_api_client==0.4.2`.

	Note that `prometheus-api-client` does not install all of its
    dependencies.  If `pip3 install prometheus-api-client==0.4.2`
    fails, you will need to install the following dependencies, either
    via your system packages or via `pip` (system packages may not
    always provide new enough dependencies).

	- A C++ compiler gcc-c++ or llvm)
	- pandas==1.1.5
	- cython
	- numpy

  - **openshift-client**: not currently packaged.  This can be
    installed via `pip3 install openshift-client`.  It provides much
    of the OpenShift client API.

    Note that `openshift-client` cannot and/or does not install all
    needed dependencies.  If `pip3 install openshift-client` fails,
    please ensure that the following dependencies are installed (this
    is current for RHEL 8.x and should be similar for other
    distributions):

	  - A C compiler (gcc or llvm)
	  - python3-libs
	  - rust
	  - setuptools-rust
	  - python3-wheel
	  - python3-pip-wheel
	  - cryptography
	  - cargo
	  - python3-devel

  Usage:

  ```
  prom-extract _options_ -- _command args..._
  ```

  Takes the following options:

  - **-u _prometheus url_**: Provide the URL to the cluster Prometheus
    server.  This normally isn't needed; the tool can find it for
    itself.

  - **-t _prometheus token_**: Provide the authentication token for
    the cluster Prometheus server.  This normally isn't needed.
    Currently, username/password authentication is not needed.

  - **-s _timestep_**: Reporting time step for metrics in seconds;
    default 30.

  - **-m _metrics profile_**: Profile of metrics to extract.  This is
    the same syntax as
    [Kube-Burner](https://kube-burner.readthedocs.io/en/latest/cli/)
    metrics profile sytax.  Default is `metrics.yaml` in the current
    directory.

  - **--epoch _relative start_**: Start the metrics collection from
    the specified period (default 1200 seconds) prior to the start of
    the job run.

  - **--post-settling-time _seconds_**: Continue collecting metrics
    for the specified period (default 60 seconds) after the job
    completes.

  - **--json-from-command**: Assume that the stdout from the command
    is well-formed JSON, and embed that JSON in the report.

	If the JSON output contains a key named `results`, it will be
    copied into a `results` key in the report; otherwise the entire
    JSON contents will be copied into `results`.

	If the JSON output contains a key named `api_objects`, these will
    be copied into the report.  `api_objects` should be a list of
    entries, each of which contains keys `name`, `kind`, and
    `namespace`.  These objects should be in existence after the job
    exits, so that they can be queried via the equivalent of `oc get
    -ojson ...`.  Pods have abbreviated data included; other objects
    are fully included.  These resources are not deleted.

	Any remaining objects in the JSON output are copied into a
    `run_data` key.

  - **--uuid _uuid_**: Use the specified UUID as the index for the
    report.  If not provided, one is generated and reported on
    stderr.  This is useful for e. g. indexing the report into a
    database.

## General information tools

- **openshift-release-info** -- get various information about one or
  more releases.

- **get-container-status**: retrieve the status of each running
  container on the cluster.

- **get-images**: retrieve the image and version of each image used by
  the cluster.

## PBench orchestration

- **bench-army-knife** -- orchestrate
  [PBench](https://github.com/distributed-system-analysis/pbench)
  under OpenShift or Kubernetes.

  Please see [pbench/README.md](pbench/README.md) for more information.

  bench-army-knife provides a way to run workloads under PBench
  without any requirement to ssh from the pbench controller to pbench
  agents.  The only requirement is to be able to ssh from the agents
  to the bench-army-knife controller (which runs the pbench
  controller).  This is done by having the agents ssh to the
  bench-army-knife controller to open a tunnel back to the agent by
  means of customizing the ssh configuration.  The Tool Meister
  orchestration in PBench at present does not completely eliminate the
  need to ssh to the agents; bench-army-knife does.

  This also provides a way to run agents either within worker pods or
  standalone on worker nodes, or both.  The latter is useful if one is
  running a workload inside a VM under OpenShift, allowing capture of
  information both from the node (host) and the pod (running inside
  the guest).

  The bench-army-knife controller can be run either outside the
  cluster or in a separate pod inside the cluster, as desired.  The
  bench-army-knife controller listens for the desired number of
  connections from agents and runs `pbench-register-tool` and/or
  `pbench-register-tool-set` followed by the workload, and when
  everything is complete runs `pbench-move-results` to save away the
  data.

  Included is a container based on the PBench container image with
  some additional tools, and the necessary pieces required for
  bench-army-knife to operate.  These include:

  - **bootstrap.sh** -- run a passed-in command within the
    bench-army-knife container environment

  - **run-pbench-agent-container** -- run the pbench agent within a
    bench-army-knife container

  - **run-pbench-controller** -- operate pbench controller functions
    within a bench-army-knife container

  - **Dockerfile.base**, **Dockerfile** -- dockerfiles for building
    the images with just RPMs and with other files needed for
    bench-army-knife.  The base image (bench-army-base) is not
    sufficient for running bench-army-knife.

  The container image can be used to run benchmarks without PBench, too.

a flexible CentOS 8 based container that
  contains pbench, fio, uperf, and many performance tools.  The
  container using this image should usually be run with `bootstrap.sh`
  as its command.  This takes the name of a file to run, along with
  that file's arguments.  The file is normally mounted into a
  container.  Among other things, it provides a convenient way to wrap
  a benchmark (or other) run without having to either create a
  separate image or pass it in on the command line itself.

  When using OpenShift or Kubernetes, the easiest way to pass the
  script in is via a configmap.  For example:


```
$ oc create configmap systemconfigmap-cb-0 --from-file=/home/me/mytest

$ oc apply -F - <<'EOF'
spec:
  containers:
  - name: "c0"
    imagePullPolicy: Always
    image: "quay.io/rkrawitz/bench-army-knife:latest"
    command:
    - bootstrap.sh
    args:
    - "/etc/bootstrap/mytest"
    - "arg0"
    - "arg1"
    volumeMounts:
    - name: "systemconfigmap-cb-0"
      mountPath: "/etc/bootstrap"
      readOnly: true
  volumes:
  - name: "systemconfigmap-cb-0"
    configMap:
      name: "systemconfigmap-cb-0"
EOF
```

## oinst API

### Introduction

The API for `oinst` consists of a platform plugin handling API calls
through a dispatch function.  Platform plugins are bash scripts source
by `oinst`.

Each supported platform must provide a plugin residing in
`installer/platforms/` (or
`$OPENSHIFT_OINST_LIBDIR/share/OpenShift/installer/platforms/`).
`OPENSHIFT_OINST_LIBDIR` may be a path, in which case each directory on
the path is searched.  The name of the file is taken to be the name of
the platform.  Autosave/backup files are not searched.

The platform plugin must provide a dispatch function, typically named
`_____<platform>_dispatch`, that handles the API calls, which will be
presented below.  Responses to API calls are provided by text on
stdout and the status (return) code; errors may be logged to stderr.

Note that all names visible at global scope (i. e. not defined with
`local` within a shell function) must start with `_____<platform>` or
`______<platform>` (five or six underscores).  Any other names result
in an error.  Any state you want to save must be in variables declared
via `declare -g`, as described in the bash man page.

All plugins must call, from top level

```
add_platform _____<platform>_dispatch
```

to register the plugin.  As noted, the dispatch function is typically
named `dispatch`, but need not be as long as the global scope rule is
followed.  If `add_platform` is not called, or the platform name does
not match the filename, the plugin is ignored.

If a platform plugin wishes to make options available to the user via
`-X option=value` (or `--option=value`), it must call

```
register_options [options...]
```

All options must start with the platform name.  These options are
dispatched as described below.

### API calls

All routines here may make use of any variables and functions in the
`oinst` script that do not start with an underscore.  They are all of
the form

**operation** [_args_]

- **base_domain** *domainname* -- specify the DNS domain name of the
  cluster to be created.

- **cleanup** -- perform any platform-specific cleanup functions.
  Generally `openshift-installer` will perform cleanup; this may be
  used for backup or if anything else needs to be done.

- **default_install_type** -- returns the default installation type.
  This may be used if e. g. a plugin supports installation to multiple
  zones, and the plugin wishes to specify one of them as the default
  (perhaps picked at random).

- **diagnose** *text* -- attempt to recognize any errors in the
  installer's output stream, to generate later diagnostics if the
  installer fails.  If the line is recognized, the diagnostic routine
  should call

  ```
  set_diagnostic <diagnostic-name> <diagnostic-routine>
  ```

  The `diagnostic-name` is the name that the diagnostic routine will
  use to recognize that the particular diagnostic was set.  The
  `diagnostic-name` and `diagnostic-routine`'s name must follow the
  naming requirements above.

  If installation fails, the `diagnostic-routine` will be invoked with
  the `diagnostic-name`.  It should print an appropriate error message
  to stdout, with an additional newline at the end.  If the return
  status is `1`, the diagnostic is taken as authoritative; default
  diagnostics related to credentials are not printed in that case.  If
  the diagnosis is less certain, the `diagnostic-routine` should
  return `0`.

- **is_install_type** *install_type* -- return a status of 0 if the
  name of the install type is recognized by this plugin, in which case
  this plugin will handle all future API calls.  If it does not
  recognize the name of this installation type, it should return 1.

- **machine_cidr** -- print the desired machine CIDR value.

- **master** -- print any additional YAML that should be supplied in
  the `controlPlane` definition.  The YAML code will be indented
  appropriately.

- **platform** -- print any additional YAML that should be supplied in
  the `platform` definition.

- **worker** -- print any additional YAML that should be supplied in
  the `compute` definition.

- **postinstall** -- perform any additional steps that are needed
  after installation successfully completes.  This may include
  installation of e. g. extra DNS or routing beyond the normal `oc login`.
  It does not need to include creation of an ssh bastion.

- **replicas** *node-type* -- echo the number of replicas desired.
  *node-type* will be either `master` or `worker`.  This routine may
  call `cmdline_replicas *node-type* *default* to use the number of
  replicas requested on the command line, along with the desired
  platform-specific default.

- **set_option** *option* *value* -- set the specified option to the
  desired value.

- **setup** -- perform any necessary setup rasks prior to installation
  (e. g. cleaning additional caches beyond the standard, setting any
  top level variables to non-default values).

- **supports_bastion** -- return a status of 0 (normal return) if the
  platform supports a bastion ssh host, or 1 (failure return) if it
  does not.

- **validate** -- perform any platform-specific validation.  This
  routine may exit (by calling `fatal`) with an appropriate error
  message.

  A typical validation may involve validating the instance type used
  in the installation.  See [Validating Instance
  Types](#validating-instance-types) below.

- **platform_help** *type* -- provide platform-specific help
  information that will be appended to the help message.  Copy one of
  the other help routines for starters.  An unknown *type* should be
  ignored.

  - **install_types** -- provide a list of install types supported by
    the platform (e. g. cloud provider zones).  Conventionally, the
    first line is flush to the left and indicates the default; other
    supported installation types are indented two spaces.

  - **default_domain** -- provide the default installation domain to
    be used.

  - **options** -- provide text with a help message for
    platform-specific options registered via `register-options`.

If the dispatch function is called with an operation that it does not
know about, it may call `dispatch_unknown <platform> <args>` to notify
that it was called invalidly (and that probably the platform needs to
be fixed).  This should only be done if it is called with an argument
outside of the list above; operations that it knows about but simply
doesn't so anything with should simply be ignored.

### Validating Instance Types

Cloud providers typically offer a variety of machine instance types
with differing amounts of memory, CPU, storage, network bandwidth,
etc.  Validating these instance types up front saves considerable
time.  Validation failure is considered to be a soft error; the user
may continue, but is warned that the chosen instance type is not known
to be valid.  This allows the user to specify e. g. a new instance
type that hasn't been added to the validation list yet.

If the platform validation function wishes to validate the instance
type, it should call

```
validate_instance_type "$worker_type" $master_type" <platform> <option_to_use> <instance_splitter> [instance names...]
```

The arguments to this function are:

- **worker_type** is the worker type specified on the command line;
  normally it should be passed literally as `"$worker_type"`

- **master_type** is the master type specified on the command line;
  normally it should be passed literally as `"$master_type"`

- **platform** is the name of the platform that should be presented in
  a help message (which may be different, or capitalized differently,
  from the defined platform name)

- **option_to_use** is the name of the option to use if the user wants
  to get a list of known valid instance types.  Assuming that
  `option_to_use` is `master_type`, the help will suggest specifying
  `--master_type=list` for a short list of instance types, or
  `--master_type=list-all` for the full list.  `master_type` is
  usually fine to use here.

- **instance_splitter** is the name of a shell function that splits
  each instance name into a type name and instance size or similar
  (subtype).  It should print two lines, the first being the name of
  the type and the second being the instance size/subtype.  The
  function should do the splitting appropriately for the cloud
  provider's nomenclature.  For example, for AWS `m5.xlarge` would be
  split into

  ```
  m5
  xlarge
  ```
- **instance names** (all other arguements on the command line) is a
  list of known instance names.  Instance type names are used to
  determine where to split lines, so all instances of a given type
  should be grouped together.  There are some special names that may
  be provided for grouping; all of these should be prefixed with a
  space:

  - **" X.Family"** is the name of a broader family of instance types,
    e. g. general purpose, compute optimized, etc.  If the user
    specifies `list`, only the first family in the lists's members are
    printed; if the user specifes `list-all`, all instance types are
    printed.

  - **" Y.Instance Type"** is the name of a particular instance that
    should be treated as its own family (not split) and always printed
    at the left on its own line.

  If the type name is a single space, the family name is treated as
  being empty and is not printed.

If the validator function recognizes the type name but not the
instance size name, it will list the known instance sizes as
suggestions.
