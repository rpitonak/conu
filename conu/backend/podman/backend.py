"""
This is backend for podman engine
"""
import logging

from conu.apidefs.backend import Backend
from conu.backend.podman.container import PodmanContainer
from conu.backend.podman.image import PodmanImage, PodmanImagePullPolicy
from conu.backend.podman.constants import CONU_ARTIFACT_TAG
from conu.backend.podman.utils import inspect_to_metadata, inspect_to_container_metadata, graceful_get


from conu.utils import run_cmd

logger = logging.getLogger(__name__)


def parse_reference(reference):
    """
    parse provided image reference into <image_repository>:<tag>

    :param reference: str, e.g. (registry.fedoraproject.org/fedora:27)
    :return: collection (tuple or list), ("registry.fedoraproject.org/fedora", "27")
    """
    if ":" in reference:
        im, tag = reference.rsplit(":", 1)
        if "/" in tag:
            # this is case when there is port in the registry URI
            return (reference, "latest")
        else:
            return (im, tag)

    else:
        return (reference, "latest")


class PodmanBackend(Backend):
    """
    For more info on using the Backend classes, see documentation of
    the parent :class:`conu.apidefs.backend.Backend` class.
    """
    name = "podman"
    ContainerClass = PodmanContainer
    ImageClass = PodmanImage

    def __init__(self, logging_level=logging.INFO, logging_kwargs=None, cleanup=None):
        """
        This method serves as a configuration interface for conu.

        :param logging_level: int, control logger verbosity: see logging.{DEBUG,INFO,ERROR}
        :param logging_kwargs: dict, additional keyword arguments for logger set up, for more info
                                see docstring of set_logging function
        :param cleanup: list, list of cleanup policy values, examples:
            - [CleanupPolicy.EVERYTHING]
            - [CleanupPolicy.VOLUMES, CleanupPolicy.TMP_DIRS]
            - [CleanupPolicy.NOTHING]
        """

        super(PodmanBackend, self).__init__(
            logging_level=logging_level, logging_kwargs=logging_kwargs, cleanup=cleanup)

    def cleanup_containers(self):
        #  FIXME: Test this
        conu_containers = self._list_podman_containers(filter=CONU_ARTIFACT_TAG)
        for c in conu_containers:
            logger.info("Trying to remove conu container: %s" % c)
            logger.debug("Removing container %s created by conu", c)
            run_cmd(["podman", "stop", c])
            run_cmd(["podman", "rm", c])

    def list_containers(self):
        """
        List all available podman containers.

        :return: collection of instances of :class:`conu.PodmanContainer`
        """
        containers = []
        for identifier in self._list_podman_containers():
            inspect_data = PodmanContainer._inspect(identifier)
            name = graceful_get(inspect_data, "Name")
            image_id = graceful_get(inspect_data, "ImageID")
            image_name, image_tag = parse_reference(graceful_get(inspect_data, "ImageName"))

            image = PodmanImage(image_name, tag=image_tag, identifier=image_id)
            container = PodmanContainer(image, identifier, name=name)
            inspect_to_container_metadata(container.metadata, inspect_data, image)
            containers.append(container)

        return containers

    def list_images(self):
        """
        List all available podman images.

        :return: collection of instances of :class:`conu.PodmanImage`
        """
        images = []
        for identifier in self._list_all_podman_images():
            inspect_data  = PodmanImage._inspect(identifier)
            try:
                i_name, tag = parse_reference(graceful_get(inspect_data, "RepoTags")[0])
            except (IndexError, TypeError):
                i_name, tag = None, None
            d_im = PodmanImage(i_name, tag=tag, identifier=identifier,
                               pull_policy=PodmanImagePullPolicy.NEVER)
            inspect_to_metadata(d_im.metadata, inspect_data)
            images.append(d_im)

        return images

    @staticmethod
    def _list_all_podman_images():
        """
        Finds all podman containers
        :return: list of containers' names
        """
        cmdline = ["podman", "images"]
        output = run_cmd(cmdline, return_output=True)
        images = []
        for l in output.split("\n")[1:]:
            images.append(l.split()[2])

        return images

    @staticmethod
    def _list_podman_containers(filter=None):
        """
        Finds podman containers by filter or all containers
        :return: list of containers' names
        """
        option = ["--filter", filter] if filter else ["-a"]
        cmdline = ["podman", "ps"] + option
        output =  run_cmd(cmdline, return_output=True)
        containers = []
        for l in output.split("\n")[1:]:
            # TODO: Check if ID parsed well
            containers.append(l[:12])

        return containers
