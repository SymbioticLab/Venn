from evaluation.internal.dataloaders.utils_data import get_data_transform
from evaluation.internal.dataset_handler import *
from evaluation.commons import *
from torchvision import transforms
import os

def import_libs(dataset_name: str):
    global numba, SPEECH, BackgroundNoiseDataset, AddBackgroundNoiseOnSTFT, DeleteSTFT, FixSTFTDimension, StretchAudioOnSTFT, TimeshiftAudioOnSTFT, ToMelSpectrogramFromSTFT, ToSTFT, ChangeAmplitude, ChangeSpeedAndPitchAudio, FixAudioLength, LoadAudio, ToMelSpectrogram, ToTensor

    if dataset_name == 'google_speech':
        import numba

        from evaluation.internal.dataloaders.speech import SPEECH, BackgroundNoiseDataset
        from evaluation.internal.dataloaders.transforms_stft import (AddBackgroundNoiseOnSTFT,
                                                          DeleteSTFT,
                                                          FixSTFTDimension,
                                                          StretchAudioOnSTFT,
                                                          TimeshiftAudioOnSTFT,
                                                          ToMelSpectrogramFromSTFT,
                                                          ToSTFT)
        from evaluation.internal.dataloaders.transforms_wav import (ChangeAmplitude,
                                                         ChangeSpeedAndPitchAudio,
                                                         FixAudioLength, LoadAudio,
                                                         ToMelSpectrogram,
                                                         ToTensor)
    
def init_model(model_name: str, dataset_name: str):
    model = None
    if model_name == "resnet18":
        from evaluation.internal.models.specialized.resnet_speech import resnet18
        model = resnet18(
            num_classes=out_put_class[dataset_name],
            in_channels=1
        )
    elif model_name == "resnet34":
        from evaluation.internal.models.specialized.resnet_speech import resnet34
        model = resnet34(
            num_classes=out_put_class[dataset_name],
            in_channels=1,
        )
    elif model_name == "mobilenet_v2":
        from evaluation.internal.models.specialized.resnet_speech import \
        mobilenet_v2
        model = mobilenet_v2(num_classes=out_put_class[dataset_name])

    else:
        from evaluation.internal.models.torch_module_provider import get_cv_model
        model = get_cv_model(name=model_name, num_classes=out_put_class[dataset_name])
    return model

def init_dataset(dataset_name: str, config: dict, data_partitioner_dict: dict, test_data_partition_dict: dict):
    import_libs(dataset_name)

    if dataset_name == "femnist":
        from evaluation.internal.dataloaders.femnist import FEMNIST

        train_transform, test_transform = get_data_transform("mnist")
        train_dataset = FEMNIST(
            config['data_dir'],
            dataset='train',
            transform=train_transform
        )
        test_dataset = FEMNIST(
            config['data_dir'],
            dataset='test',
            transform=test_transform
        )
        
        train_partitioner = Data_partitioner(data=train_dataset, num_of_labels=out_put_class[dataset_name])
        train_partitioner.partition_data_helper(0, data_map_file=config['data_map_file'])
        data_partitioner_dict[dataset_name] = train_partitioner
        
        test_partitioner = Data_partitioner(data=test_dataset, num_of_labels=out_put_class[dataset_name])
        test_partitioner.partition_data_helper(0, data_map_file=config['test_data_map_file'])
        test_data_partition_dict[dataset_name] = test_partitioner
    
    elif dataset_name == "openImg":
        from evaluation.internal.dataloaders.openimage import OpenImage
        train_transform, test_transform = get_data_transform("openImg")
        train_dataset = OpenImage(
            config['data_dir'], split='train', download=False, transform=train_transform)
        test_dataset = OpenImage(
            config["data_dir"], split='val', download=False, transform=test_transform)
        
        train_partitioner = Data_partitioner(data=train_dataset, num_of_labels=out_put_class[dataset_name])
        train_partitioner.partition_data_helper(0, data_map_file=config['data_map_file'])
        data_partitioner_dict[dataset_name] = train_partitioner
        
        test_partitioner = Data_partitioner(data=test_dataset, num_of_labels=out_put_class[dataset_name])
        test_partitioner.partition_data_helper(config["client_test_num"])
        test_data_partition_dict[dataset_name] = test_partitioner

    elif dataset_name == "google_speech":
        bkg = '_background_noise_'
        data_aug_transform = transforms.Compose(
            [ChangeAmplitude(), ChangeSpeedAndPitchAudio(), FixAudioLength(), ToSTFT(), StretchAudioOnSTFT(),
                TimeshiftAudioOnSTFT(), FixSTFTDimension()])

        bg_dataset = BackgroundNoiseDataset(
            os.path.join(config['data_dir'], bkg), data_aug_transform)

        add_bg_noise = AddBackgroundNoiseOnSTFT(bg_dataset)
        train_feature_transform = transforms.Compose([ToMelSpectrogramFromSTFT(
                n_mels=32), DeleteSTFT(), ToTensor('mel_spectrogram', 'input')])

        train_dataset = SPEECH(config['data_dir'],
                               dataset='train',
                                transform=transforms.Compose(
                                    [LoadAudio(),
                                    data_aug_transform,
                                    add_bg_noise,
                                    train_feature_transform]))
        valid_feature_transform = transforms.Compose(
                [ToMelSpectrogram(n_mels=32), ToTensor('mel_spectrogram', 'input')])
        test_dataset = SPEECH(config['data_dir'], 
                            dataset='test',
                            transform=transforms.Compose(
                                [LoadAudio(),
                                FixAudioLength(),
                                valid_feature_transform]))
        train_partitioner = Data_partitioner(data=train_dataset, num_of_labels=out_put_class[dataset_name])
        train_partitioner.partition_data_helper(0, data_map_file=config['data_map_file'])
        data_partitioner_dict[dataset_name] = train_partitioner
        
        test_partitioner = Data_partitioner(data=test_dataset, num_of_labels=out_put_class[dataset_name])
        test_partitioner.partition_data_helper(0, data_map_file=config['test_data_map_file'])
        test_data_partition_dict[dataset_name] = test_partitioner