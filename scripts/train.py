import hydra
from omegaconf import DictConfig, OmegaConf
import logging

# Import your modules here
# from model.model import MyModel
# from data.dataset import create_dataloaders
# from training.trainer import Trainer

logger = logging.getLogger(__name__)

@hydra.main(config_path="../configs", config_name="config", version_base="1.3")
def main(cfg: DictConfig):
    print(OmegaConf.to_yaml(cfg))
    logger.info("Initializing project...")
    
    # 1. Instantiate Data
    # train_loader, val_loader = create_dataloaders(cfg.data)
    
    # 2. Instantiate Model
    # model = MyModel(cfg.model)
    
    # 3. Instantiate Trainer
    # trainer = Trainer(cfg, model, train_loader, val_loader)
    
    # 4. Start Training
    # trainer.train()

if __name__ == "__main__":
    main()
