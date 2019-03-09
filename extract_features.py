import os

import argparse

import torch
from torch.autograd import Variable
from torchvision import transforms
import videotransforms
import numpy as np
from pytorch_i3d import InceptionI3d
from charades_dataset_full import Charades as Dataset

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

parser = argparse.ArgumentParser()
parser.add_argument('-mode', type=str, help='rgb or flow')
parser.add_argument('-load_model', type=str)
parser.add_argument('-root', type=str)
parser.add_argument('-gpu', type=str)
parser.add_argument('-save_dir', type=str)

args = parser.parse_args()
os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu


def run(anno_rpath, video_rpath, max_steps=64e3, mode='rgb', batch_size=1,
        load_model='models/rgb_charades.pt', save_dir='output/features/'):
    # setup dataset
    test_transforms = transforms.Compose([videotransforms.CenterCrop(224)])

    dataset = Dataset(split, 'training', root, mode, test_transforms, num=-1, save_dir=save_dir)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=8,
                                             pin_memory=True)

    val_dataset = Dataset(split, 'testing', root, mode, test_transforms, num=-1, save_dir=save_dir)
    val_dataloader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size, shuffle=True, num_workers=8,
                                                 pin_memory=True)

    dataloaders = {'train': dataloader, 'val': val_dataloader}
    datasets = {'train': dataset, 'val': val_dataset}

    # setup the model
    if mode == 'flow':
        i3d = InceptionI3d(400, in_channels=2)
    else:
        i3d = InceptionI3d(400, in_channels=3)
    i3d.replace_logits(157)
    i3d.load_state_dict(torch.load(load_model))
    i3d.cuda()

    for phase in ['train', 'val']:
        i3d.train(False)  # Set model to evaluate mode

        tot_loss = 0.0
        tot_loc_loss = 0.0
        tot_cls_loss = 0.0

        # Iterate over data.
        for data in dataloaders[phase]:
            # get the inputs
            inputs, labels, name = data
            if os.path.exists(os.path.join(save_dir, name[0] + '.npy')):
                continue

            b, c, t, h, w = inputs.shape
            if t > 1600:
                features = []
                for start in range(1, t - 56, 1600):
                    end = min(t - 1, start + 1600 + 56)
                    start = max(1, start - 48)
                    ip = Variable(torch.from_numpy(inputs.numpy()[:, :, start:end]).cuda(), volatile=True)
                    features.append(i3d.extract_features(ip).squeeze(0).permute(1, 2, 3, 0).data.cpu().numpy())
                np.save(os.path.join(save_dir, name[0]), np.concatenate(features, axis=0))
            else:
                # wrap them in Variable
                inputs = Variable(inputs.cuda(), volatile=True)
                features = i3d.extract_features(inputs)
                np.save(os.path.join(save_dir, name[0]), features.squeeze(0).permute(1, 2, 3, 0).data.cpu().numpy())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-anno_rpath', type=str, help='the root path of annotations')
    parser.add_argument('-video_rpath', type=str, help='the root path of videos')
    parser.add_argument('-save_model', type=str)

    args = parser.parse_args()

    run(args.anno_rpath, args.video_rpath)
