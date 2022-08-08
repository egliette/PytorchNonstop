import pandas as pd
import torch
import logging
from torch.utils.data import DataLoader
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from dataloader.dataloaders import ShelterOutcomeDataset, DeviceDataloader
from utils.utils import get_default_device, to_device
from model.model import ShelterOutcomeModel, train_loop
from model.optimizer import get_optimizer
from logger.logger import setup_logging


def main():
    print("Setup...")
    setup_logging(save_dir='saved/log', log_config='logger/logger_config.yml')
    logger = logging.getLogger('train')
    print("Setup - Done")

    print("Data loading...")
    train_data = pd.read_csv("data/train.csv")
    test_X = pd.read_csv("data/test.csv")
    print("Data loading - Done")

    print("Data processing...")
    X = train_data.drop(columns=['AnimalID', 'OutcomeType', 'OutcomeSubtype'])
    Y = train_data['OutcomeType']
    stacked_df = X.append(test_X.drop(columns=['ID']))
    stacked_df['DateTime'] = pd.to_datetime(stacked_df['DateTime'])
    stacked_df['year'] = stacked_df['DateTime'].dt.year
    stacked_df['month'] = stacked_df['DateTime'].dt.month
    stacked_df = stacked_df.drop(columns=['DateTime'])

    for col in stacked_df.columns:
        n_nulls = stacked_df[col].isnull().sum()
        if n_nulls > 10000:
            print(f"Drop column {col} with {n_nulls} nulls")
            stacked_df = stacked_df.drop(columns=[col])

    for col in stacked_df.columns:
        if stacked_df.dtypes[col] == 'object':
            stacked_df[col] = stacked_df[col].fillna('NA')
        else:
            stacked_df[col] = stacked_df[col].fillna(0)
        stacked_df[col] = LabelEncoder().fit_transform(stacked_df[col])

    for col in stacked_df.columns:
        stacked_df[col] = stacked_df[col].astype('category')

    for col in X.columns:
        X[col] = X[col].astype('category')

    X = stacked_df[:train_data.shape[0]]
    Y = LabelEncoder().fit_transform(Y)

    train_X, valid_X, train_Y, valid_Y = train_test_split(X, Y, test_size=0.1, random_state=0)

    embedded_cols = dict()
    for name, col in X.items():
        n_categories = len(col.cat.categories)
        if n_categories > 2:
            embedded_cols[name] = n_categories
    embedded_cols_names = embedded_cols.keys()
    embedding_sizes = [(n_categories, min(50, (n_categories+1)//2)) for _, n_categories in embedded_cols.items()]
    print("Data processing - Done")

    print("DataLoaders creating...")
    train_dataset = ShelterOutcomeDataset(train_X, train_Y, embedded_cols_names)
    valid_dataset = ShelterOutcomeDataset(valid_X, valid_Y, embedded_cols_names)
    batch_size = 1000
    train_dataloader = DataLoader(train_dataset, batch_size, shuffle=True)
    valid_dataloader = DataLoader(valid_dataset, batch_size, shuffle=True)
    device = get_default_device()
    train_dl = DeviceDataloader(train_dataloader, device)
    valid_dl = DeviceDataloader(valid_dataloader, device)
    print("DataLoaders creating - Done")

    print("Model training...")
    n_cont = len(X.columns) - len(embedded_cols_names)
    model = ShelterOutcomeModel(embedding_sizes, n_cont)
    to_device(model, device)
    optim = get_optimizer(model)
    epochs = 20
    train_loop(model, train_dl, valid_dl, optim, epochs, lr=0.01, wd=0.0)
    print("Model training - Done")

    print("Model saving...")
    torch.save(model, "saved/models/saved_model.pt")
    print("Model saving - Done")

if __name__ == '__main__':
    main()