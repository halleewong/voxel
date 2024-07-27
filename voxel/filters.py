"""
Utilies for image grid filtering and kernel construction.
"""

from __future__ import annotations

import torch


def gaussian_kernel_1d(
    sigma: float,
    truncate: float = 2,
    device: torch.device | None = None,
    dtype: torch.dtype | None = None) -> torch.Tensor:
    """
    Generate a 1D Gaussian kernel with a specified standard deviation.

    Args:
        sigma (float): Standard deviations in element (voxel) space.
        truncate (float, optional): The number of standard deviations to extend
            the kernel before truncating.
        device (torch.device, optional): The device on which to create the kernel.
        device (torch.dtype, optional): The kernel datatype.

    Returns:
        Tensor: A kernel of shape $2 * truncate * sigma + 1$.
    """
    r = int(truncate * sigma + 0.5)
    x = torch.arange(-r, r + 1, device=device, dtype=dtype)
    sigma2 = 1 / torch.clip(torch.as_tensor(sigma), min=1e-5).pow(2)
    pdf = torch.exp(-0.5 * (x.pow(2) * sigma2))
    return pdf / pdf.sum()


def gaussian_blur(
    image: torch.Tensor,
    sigma: list,
    batched: bool = False,
    truncate: float = 2) -> torch.Tensor:
    """
    Apply Gaussian blurring to a data grid.

    The Gaussian filter is applied using convolution. The size of the filter kernel
    is determined by the standard deviation and the truncation factor.

    Args:
        image (Tensor): An image tensor with preceding channel dimensions. A
            batch dimension can be included by setting `batched=True`.
        sigma (float): Standard deviations in element (voxel) space.
        batched (bool, optional): If True, assume image has a batch dimension.
        truncate (float, optional): The number of standard deviations to extend
            the kernel before truncating.

    Returns:
        Tensor: The blurred tensor with the same shape as the input tensor.
    """
    ndim = image.ndim - (2 if batched else 1)

    # sanity check for common mistake
    if ndim == 4 and not batched:
        raise ValueError(f'gaussian blur input has {image.ndim} dims, '
                          'but batched option is False')

    # make sure sigmas match the ndim
    sigma = torch.as_tensor(sigma)
    if sigma.ndim == 0:
        sigma = sigma.repeat(ndim)
    if len(sigma) != ndim:
        raise ValueError(f'sigma must be {ndim}D, but got length {len(sigma)}')

    blurred = image.float()
    if not batched:
        blurred = blurred.unsqueeze(0)

    for dim, s in enumerate(sigma):

        # reuse previous kernel if we can
        if dim == 0 or s != sigma[dim - 1]:
            kernel = gaussian_kernel_1d(s, truncate, blurred.device, blurred.dtype)
        
        # kernels are normalized. if the length is one, there's no point in using it
        if len(kernel) == 1:
            continue

        # apply the convolution
        slices = [None] * (ndim + 2)
        slices[dim + 2] = slice(None)
        kernel_dim = kernel[slices]
        conv = getattr(torch.nn.functional, f'conv{ndim}d')
        blurred = conv(blurred, kernel_dim, groups=image.shape[0], padding='same')

    if not batched:
        blurred = blurred.squeeze(0)

    return blurred