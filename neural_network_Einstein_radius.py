#### 2019.1.8 on HSR Taiwan

import torch
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset
from  torch.autograd import Variable
import torch.optim as optim
from torchvision import datasets, transforms
import torchvision.models as models
import os, sys
import pandas as pd
import numpy as np
from tqdm import tqdm
from tensorboardX import SummaryWriter
import astropy
from astropy.io import fits
from astropy.table import Table
import pandas as pd
import csv
import numpy as np
import scipy as sp
import scipy.ndimage
import h5py
from scipy.ndimage import gaussian_filter
from scipy.ndimage import rotate
import matplotlib.pyplot as plt
import time
import gc
import datetime
import matplotlib.pyplot as plt
from astropy.coordinates import search_around_sky, SkyCoord
from astropy import units as u
from sklearn.model_selection import train_test_split
from PIL import Image



root_folder = "/media/joshua/HDD_fun2/Public/"
save_model_path = './saved_model/'


EPOCH = 100
glo_batch_size = 50
test_num_batch = 50

normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],std=[0.229, 0.224, 0.225])
# data_transform = transforms.Compose([
#             transforms.ToTensor(), # scale to [0,1] and convert to tensor
#             normalize,
#             ])

data_transform = transforms.Compose([
            transforms.ToTensor(), # scale to [0,1] and convert to tensor
            normalize,
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.5),
            transforms.RandomRotation(45),
])
target_transform = torch.Tensor


class LensDataset(Dataset): # torch.utils.data.Dataset
    def __init__(self, root_dir, train=True, transform=None, target_transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.target_transform = target_transform
        self.train = train# training set or test set


        if self.train:
            self.path = root_dir#os.path.join(self.root_dir, self.train_folder)
            self.df = pd.read_csv(self.path + '/Einstein_area_train.csv')

        else:
            self.path = root_dir#os.path.join(self.root_dir, self.test_folder)
            self.df = pd.read_csv(self.path + '/Einstein_area_val.csv')

    def __getitem__(self, index):

        #print(self.df['ID'])
        ID = self.df['ID'].iloc[[index]]
        #n_sources = self.df['n_sources'].iloc[[index]]
        channel_names = ['EUC_H', 'EUC_J', 'EUC_Y', 'EUC_VIS']
        ein_area = self.df['ein_area'].iloc[[index]]  ### square rad
        Einstein_Radius = (180/np.pi) * 3600. * (ein_area**0.5) # in arcsec
        #print("Einstein_Radius", Einstein_Radius.values[0])
        #print("mag_eff", mag_eff.values[0])

        #if
        #Einstein_Radius = 1
        # filepath = "/media/joshua/HDD_fun2/Public/EUC_Y/imageEUC_Y-" + str(ID.values[0]) + ".fits"
        # lens_data = fits.open(filepath)
        # img = lens_data[0].data
        image = np.zeros((4, 224, 224))
        try:
            for i, channel in enumerate(channel_names):

                filepath = self.path + channel + "/image" + channel + "-" + str(ID.values[0]) + ".fits"
                lens_data = fits.open(filepath)
                img = lens_data[0].data
                img *= 10e8
                img_channel_0 = scipy.ndimage.zoom(img, 224/img.shape[0], order=1)
                image[i, :, :] += img_channel_0
        except:
            print("error", ID)
            pass



        # if self.transform is not None:
        #     #image = image.astype(np.uint8)
        #     print(image.dtype)
        #     image = Image.fromarray(image)
        #     #test_data = data_transforms['test'](transforms.ToPILImage()(test_data))
        #     image = self.transform(image)

        return image, Einstein_Radius.values[0]#n_sources.values[0]

    def __len__(self):
        return self.df.shape[0]


train_loader = torch.utils.data.DataLoader(LensDataset(root_folder, train=True, transform=data_transform, target_transform=target_transform),
                    batch_size = glo_batch_size, shuffle = True)

if __name__ == '__main__':

    if not os.path.exists(save_model_path):
        os.mkdir(save_model_path)

    dset_classes_number = 1
    num_input_channel = 4
    net = models.resnet18(pretrained=False)
    net.conv1 = nn.Conv2d(num_input_channel, 64, kernel_size=7, stride=2, padding=3, bias=False)
    num_ftrs = net.fc.in_features
    #new_num_features = *something bigger than 512*
    net.fc= nn.Linear(in_features=num_ftrs, out_features=dset_classes_number)
    #loss_fn = nn.BCEWithLogitsLoss(reduction='elementwise_mean')
    loss_fn = nn.MSELoss(reduce=True, size_average=True)

    net.cuda()

    optimizer = optim.Adam(net.parameters(), lr = 1e-4)
    tb = SummaryWriter()

    best_accuracy = float("inf")

    # for batch_idx, (data, n_sources) in enumerate(tqdm(train_loader, total = len(train_loader))):
    #     data, target = data.float(), n_sources.float()
    #     data, target = Variable(data).cuda(), Variable(target).cuda()
    #     if batch_idx > 10:
    #         break
    for epoch in range(EPOCH):

        net.train()
        total_loss = 0.0
        total_counter = 0
        total_rms = 0

        for batch_idx, (data, Einstein_Radius) in enumerate(tqdm(train_loader, total = len(train_loader))):
            data, target = data.float(), Einstein_Radius.float()
            data, target = Variable(data).cuda(), Variable(target).cuda()
            data, target = data, target.unsqueeze(1)
            #print("data shape", data.shape)
            #print("data", sum(sum(data)))
            # plt.imshow(data.data.cpu().numpy()[0,0,:,:])
            # plt.colorbar()
            # plt.show()
            #print("target:",target)
            optimizer.zero_grad()
            output = net(data)
            #print("output:", output)
            loss = loss_fn(output, target)
            #m = nn.Sigmoid()
            square_diff = ((output) - target) #((output - target)**2)**(0.5)
            total_rms += square_diff.std(dim=0)
            total_loss += loss.item()
            total_counter += 1

            loss.backward()
            optimizer.step()

            del target
            del data
            gc.collect()
            # if batch_idx % 2 == 0 and batch_idx != 0:
            #     #tb.add_scalar('test_loss', loss.item())
            #     break

        # Collect RMS over each label
        avg_rms = total_rms / (total_counter)
        avg_rms = avg_rms.cpu()
        avg_rms = (avg_rms.data).numpy()
        for i in range(len(avg_rms)):
            tb.add_scalar('rms %d' % (i+1), avg_rms[i])

        # print test loss and tets rms
        print(epoch, 'Train loss (averge per batch wise):', total_loss/(total_counter), ' RMS (average per batch wise):', np.array_str(avg_rms, precision=3))

        with torch.no_grad():
            net.eval()
            total_loss = 0.0
            total_counter = 0
            total_rms = 0

            test_loader = torch.utils.data.DataLoader(LensDataset(root_folder, train=False, transform=data_transform, target_transform=target_transform),
                        batch_size = glo_batch_size, shuffle = True
                        )

            # for batch_idx, (data, n_sources) in enumerate(tqdm(train_loader, total = len(train_loader))):
            #     data, target = data.float(), mdot.float()
            #     data, target = Variable(data).cuda(), Variable(target).cuda()
            #     data, target = data, target.unsqueeze(1)
            for batch_idx, (data, Einstein_Radius) in enumerate(test_loader):
                data, target = data.float(), Einstein_Radius.float()
                data, target = Variable(data).cuda(), Variable(target).cuda()
                data, target = data, target.unsqueeze(1)




                #pred [batch, out_caps_num, out_caps_size, 1]
                pred = net(data)
                loss = loss_fn(pred, target)
                #m = nn.Sigmoid()
                square_diff = ((pred) - target)
                total_rms += square_diff.std(dim=0)
                total_loss += loss.item()
                total_counter += 1
                gc.collect()

                if batch_idx % test_num_batch == 0 and batch_idx != 0:
                    tb.add_scalar('test_loss', loss.item())
                    break

            # Collect RMS over each label
            avg_rms = total_rms / (total_counter)
            avg_rms = avg_rms.cpu()
            avg_rms = (avg_rms.data).numpy()
            for i in range(len(avg_rms)):
                tb.add_scalar('rms %d' % (i+1), avg_rms[i])

            # print test loss and tets rms
            print(epoch, 'Test loss (averge per batch wise):', total_loss/(total_counter), ' RMS (average per batch wise):', np.array_str(avg_rms, precision=3))
            if total_loss/(total_counter) < best_accuracy:
                best_accuracy = total_loss/(total_counter)
                datetime_today = str(datetime.date.today())
                torch.save(net, save_model_path + datetime_today + 'Einstein_Radius_' +'resnet18.mdl')
                print("saved to " + "Einstein_Radius_resnet18.mdl" + " file.")

tb.close()
