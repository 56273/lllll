# XML Injector version 2
# by Scumbumbo @ MTS
#
# The snippet module defines the tuning classes to load the XmlInjector snippet XML.  Once
# the tuning has been loaded by the game, the _tuning_loaded_callback invokes the functions
# in the add_to_tuning module to process the affordance additions.
#
# This mod is intended as a standard for modder's to use as a shared library.  Please do not
# distribute any modifications anywhere other than the mod's main download site.  Modification
# suggestions and bug notices should be communicated to the maintainer, currently Scumbumbo at
# the Mod The Sims website - http://modthesims.info/member.php?u=7401825
#

# ----------
# September 5th, 2019 patch broke some of the injections. Per the guidance of Deaderpool, the patch changed how ImmutableSlots can be accessed, such that, for example, "entry['object_selection']" needs to be "entry.object_selection"
# This appears to be the cause of some injections not working.
# I've made changes in the _tuning_loaded_callback method to reflect this and verified most injections working again, since Scumbumbo was not around to fix it (a few were not explicitly tested, but are assumed to be working).
# In keeping with the requested official distribution channels, I'm posting the fixed version in the comments of the mod's official page on Mod The Sims website.
# - Triplis
# ----------

import services
import sims4.log
from buffs.tunable import TunableBuffReference
from interactions.utils.loot import LootActionVariant
from interactions.utils.loot_ops import DoNothingLootOp
from interactions.utils.outcome_enums import OutcomeResult
from objects.components.state import TunableStateComponent
from objects.components.name_component import NameComponent
from objects.components.object_relationship_component import ObjectRelationshipComponent
from objects.definition_manager import DefinitionManager
from sims4.resources import Types
from traits.traits import Trait
from sims4.tuning.instances import HashedTunedInstanceMetaclass
from sims4.tuning.tunable import AutoFactoryInit, HasTunableSingletonFactory, Tunable, \
    TunableTuple, TunableList, TunableReference, TunableVariant, TunableEnumEntry, OptionalTunable, TunableResourceKey
from tag import Tag
from tunable_multiplier import TunableMultiplier
from ui.ui_dialog import UiDialogOk, PhoneRingType, UiDialogOption, UiDialogStyle
from rewards.reward_tuning import TunableSpecificReward
from sims4.tuning.tunable import TunableMapping
from satisfaction.satisfaction_tracker import SatisfactionTracker
from interactions.base.picker_interaction import DefinitionsFromTags, DefinitionsExplicit, InventoryItems, DefinitionsRandom, DefinitionsTested
import tag
from sims4.localization import TunableLocalizedString

import xml_injector.add_to_tuning
import xml_injector.version

import traceback
import inspect

logger = sims4.log.Logger('XmlInjector')


class ObjectSelection(TunableVariant):
    # object_list variant
    class _ObjectList(HasTunableSingletonFactory, AutoFactoryInit):
        FACTORY_TUNABLES = {
            'object_list': TunableList(
                description='A list of objects to add the interactions to',
                tunable=Tunable(
                    description='Reference to an object tuning instance',
                    tunable_type=int,
                    default=None)
            )
        }

        def get_objects(self):
            # Get the object tunings for each of the objects in the object list
            # from the DefinitionManager
            definition_manager = services.definition_manager()
            obj_list = []
            for obj_id in self.object_list:
                # get() on the DefinitionManager will return an object definition,
                # to get an actual tuning by ID, we need to call the super()
                tun = super(DefinitionManager, definition_manager).get(obj_id)
                if tun:
                    if hasattr(tun, '_super_affordances'):
                        obj_list.append(tun)
            return obj_list

    # objects_with_affordance variant
    class _ObjectsWithAffordance(HasTunableSingletonFactory, AutoFactoryInit):
        FACTORY_TUNABLES = {
            'affordance': TunableReference(
                description='Reference to an interaction tuning instance',
                manager=services.affordance_manager(),
                class_restrictions=('SuperInteraction',),
                allow_none=False,
                pack_safe=True)
        }

        def get_objects(self):
            # Iterate through all object tunings from the DefinitionManager
            # and return those that contain the referenced affordance
            definition_manager = services.definition_manager()
            obj_list = []
            for tun in definition_manager._tuned_classes.values():
                if hasattr(tun, '_super_affordances') and self.affordance in tun._super_affordances:
                    obj_list.append(tun)
            return obj_list

    # objects_matching_name variant
    class _ObjectsMatchingName(HasTunableSingletonFactory, AutoFactoryInit):
        FACTORY_TUNABLES = {
            'partial_name': Tunable(
                description='A string specifying the partial name of objects to select',
                tunable_type=str,
                default=None)
        }

        def get_objects(self):
            # Iterate through all object tunings from the DefinitionManager
            # and return those whose name contains the partial_name
            obj_list = []
            if not isinstance(self.partial_name, str):
                logger.error('Tuning error, missing or invalid partial_name')
            else:
                definition_manager = services.definition_manager()
                for tun in definition_manager._tuned_classes.values():
                    if hasattr(tun, '__name__') and self.partial_name in tun.__name__:
                        obj_list.append(tun)
            return obj_list

    # objects_with_tag variant
    class _ObjectsWithTag(HasTunableSingletonFactory, AutoFactoryInit):
        FACTORY_TUNABLES = {
            'tag': TunableEnumEntry(
                description='A tag to search for object selection.',
                tunable_type=Tag,
                default=Tag.INVALID)
        }
        
        def get_objects(self):
            obj_set = set()
            definition_manager = services.definition_manager()
            definition_manager.refresh_build_buy_tag_cache(refresh_definition_cache=False)
            for defn in definition_manager.get_definitions_for_tags_gen((self.tag,)):
                obj_set.add(defn.cls)
            return list(obj_set)

    # Create a variant for the object_selection
    def __init__(self, **kwargs):
        super().__init__(
            object_list=ObjectSelection._ObjectList.TunableFactory(),
            objects_with_affordance=ObjectSelection._ObjectsWithAffordance.TunableFactory(),
            objects_matching_name=ObjectSelection._ObjectsMatchingName.TunableFactory(),
            objects_with_tag=ObjectSelection._ObjectsWithTag.TunableFactory(),
            default=None,
            **kwargs)


# XmlInjector snippet tuning class
class XmlInjector(metaclass=HashedTunedInstanceMetaclass,
                  manager=services.get_instance_manager(Types.SNIPPET)):
    INSTANCE_TUNABLES = {
        'xml_injector_minimum_version': Tunable(
            description='The minimum version of XML Injector required to process your snippet.',
            tunable_type=int,
            default=1
        ),
        'version_error_dialog': OptionalTunable(
            description='If enabled, override the default version error dialog with your own.',
            tunable=UiDialogOk.TunableFactory(
                description='The dialog to display if this snippet requires a newer version of the injector.',
                locked_args={'audio_sting': None, 'dialog_options': UiDialogOption.DISABLE_CLOSE_BUTTON,
                             'dialog_style': UiDialogStyle.DEFAULT, 'icon': None, 'icon_override_participant': None,
                             'phone_ring_type': PhoneRingType.NO_RING, 'secondary_icon': None, 'text_tokens': None,
                             'timeout_duration': None, 'ui_responses': ()}
            )
        ),
        'add_interactions_to_objects': TunableList(
            description='A list of object and interaction lists',
            tunable=TunableTuple(
                object_selection=ObjectSelection(),
                _super_affordances=TunableList(
                    description='A list of interactions to add to the objects',
                    tunable=TunableReference(
                        description='Reference to an interaction tuning instance',
                        manager=services.affordance_manager(),
                        class_restrictions=('SuperInteraction',),
                        allow_none=False,
                        pack_safe=True)
                )
            ),
            allow_none=False,
            unique_entries=True
        ),
        'add_interactions_to_sims': TunableList(
            description='A list of interactions to add to the object_sim',
            tunable=TunableReference(
                description='Reference to an interaction tuning instance',
                manager=services.affordance_manager(),
                class_restrictions=('SuperInteraction',),
                allow_none=False,
                pack_safe=True),
            allow_none=False,
            unique_entries=True
        ),
        'add_interactions_to_phones': TunableList(
            description='A list of interactions to add to sim phones',
            tunable=TunableReference(
                description='Reference to an interaction tuning instance',
                manager=services.affordance_manager(),
                allow_none=False,
                pack_safe=True),
            allow_none=False,
            unique_entries=True
        ),
        'add_interactions_to_relationship_panel': TunableList(
            description='A list of interactions to add to the relationship panel',
            tunable=TunableReference(
                description='Reference to an interaction tuning instance',
                manager=services.affordance_manager(),
                allow_none=False,
                pack_safe=True),
            allow_none=False,
            unique_entries=True
        ),
        'add_mixer_interactions': TunableList(
            description='A list of mixer_snippet and interaction lists',
            tunable=TunableTuple(
                mixer_snippets=TunableList(
                    description='A list of AffordanceLists to add the interactions to',
                    tunable=TunableReference(
                        description='Reference to an AffordanceList snippet tuning instance',
                        manager=services.get_instance_manager(Types.SNIPPET),
                        class_restrictions=('AffordanceList',),
                        allow_none=False,
                        pack_safe=True)
                ),
                affordances=TunableList(
                    description='A list of interactions to add to the mixers',
                    tunable=TunableReference(
                        description='Reference to an interaction tuning instance',
                        manager=services.affordance_manager(),
                        allow_none=False,
                        pack_safe=True)
                )
            ),
            allow_none=False,
            unique_entries=True
        ),
        'add_to_loot_actions': TunableList(
            description='A list of LootAction references and LootActionVariant to add',
            tunable=TunableTuple(
                loot_actions_ref=TunableReference(
                    description='Reference to a LootAction tuning instance',
                    manager=services.get_instance_manager(Types.ACTION),
                    class_restrictions=('LootActions',),
                    pack_safe=True),
                loot_actions_to_add=TunableList(
                    description='List of loots operations that will be awarded.',
                    tunable=LootActionVariant(
                        statistic_pack_safe=True
                    )
                )
            ),
            allow_none=False
        ),
        'add_to_random_loot_actions': TunableList(
            description='A list of RandomWeightedLoot references and LootActionVariant/weights to add',
            tunable=TunableTuple(
                random_weighted_loot_ref=TunableReference(
                    description='Reference to a RandomWeightedLoot tuning instance',
                    manager=services.get_instance_manager(Types.ACTION),
                    class_restrictions=('RandomWeightedLoot',),
                    pack_safe=True),
                random_loot_actions_to_add=TunableList(
                    description='List of weighted loot actions that can be run.',
                    tunable=TunableTuple(
                        description='Weighted actions that will be randomly selected when the loot is executed.  The loots will be tested before running to guarantee the random action is valid.',
                        action=LootActionVariant(
                            do_nothing=DoNothingLootOp.TunableFactory()
                        ),
                        weight=TunableMultiplier.TunableFactory(
                            description='The weight of this potential initial moment relative to other items within the new merged list.'
                        )
                    )
                )
            ),
            allow_none=False
        ),
        'add_states_to_objects': TunableList(
            description='A list of object and states lists',
            tunable=TunableTuple(
                object_selection=ObjectSelection(),
                state_component=TunableStateComponent(
                    locked_args={'delinquency_state_changes': None, 'overlapping_slot_states': None,
                                 'timed_state_triggers': None, 'unique_state_changes': None}
                )
            ),
            allow_none=False
        ),
        'add_name_component_to_objects': TunableList(
            description='A list of object and name components',
            tunable=TunableTuple(
                object_selection=ObjectSelection(),
                name_component=NameComponent.TunableFactory()
            ),
            allow_none=False
        ),
        'add_object_relationships_to_objects': TunableList(
            description='A list of object and object relationships',
            tunable=TunableTuple(
                object_selection=ObjectSelection(),
                object_relationships_component=ObjectRelationshipComponent.TunableFactory(
                    locked_args={'icon_override': None}
                )
            ),
            allow_none=False
        ),
        # For adding to the "locked" set of interactions on a computer (or any other future lockable objects like them)
        'add_lock_aware_interactions_to_lockable_objects': TunableList(
            description='A list of object and interaction lists',
            tunable=TunableTuple(
                object_selection=ObjectSelection(),
                super_affordances=TunableList(
                    description='A list of interactions to add to the objects',
                    tunable=TunableReference(
                        description='Reference to an interaction tuning instance',
                        manager=services.affordance_manager(),
                        class_restrictions=('SuperInteraction',),
                        allow_none=False,
                        pack_safe=True)
                )
            ),
            allow_none=False
        ),
        'add_buffs_to_trait': TunableList(
            description='A list of traits and buffs to add',
            tunable=TunableTuple(
                trait=TunableReference(
                    description='Reference to a Trait tuning instance',
                    manager=services.get_instance_manager(sims4.resources.Types.TRAIT),
                    class_restrictions=('Trait',),
                    pack_safe=True
                ),
                buffs=TunableList(
                    description='A list of buffs to add',
                    tunable=TunableBuffReference(pack_safe=True),
                    unique_entries=True
                )
            ),
            allow_none=False
        ),
        'add_satisfaction_store_rewards': TunableList(
            description='A list of object and object relationships',
            tunable=TunableTuple(
                new_items=TunableMapping(
                    key_type=TunableReference(
                        description='SimReward instance ID',
                        manager=services.get_instance_manager(Types.REWARD),
                        class_restrictions=('SimReward',),
                        allow_none=False,
                        pack_safe=True
                    ),
                    value_type=TunableTuple(
                        award_type=TunableEnumEntry(SatisfactionTracker.SatisfactionAwardTypes, SatisfactionTracker.SatisfactionAwardTypes.MONEY),
                        cost=Tunable(tunable_type=int, default=100)
                    )
                )
            ),
            allow_none=False
        ),
        'add_purchase_list_options_to_interactions': TunableList(
            description='A list of purchase picker interactions and purchase list options to add to them.',
            tunable=TunableTuple(
                interactions_to_add_to=TunableList(
                    description='A list of interactions to add to the relationship panel',
                    tunable=TunableReference(
                        description='Reference to an interaction tuning instance',
                        manager=services.affordance_manager(),
                        allow_none=False,
                        pack_safe=True
                    ),
                    allow_none=False,
                    unique_entries=True
                ),
                purchase_list_options=TunableList(
                    description = 'A list of methods that will be used to generate the list of objects that are available in the picker.',
                    tunable=TunableVariant(
                        description='The method that will be used to generate the list of objects that will populate the picker.', 
                        all_items=DefinitionsFromTags.TunableFactory(
                            description='Look through all the items that are possible to purchase. This should be accompanied with specific filtering tags in Object Populate Filter to get a good result.'
                        ), 
                        specific_items=DefinitionsExplicit.TunableFactory(
                            description='A list of specific items that will be purchasable through this dialog.'
                        ), 
                        inventory_items=InventoryItems.TunableFactory(
                            description='Looks at the objects that are in the inventory of the desired participant and returns them based on some criteria.'
                        ), 
                        random_items=DefinitionsRandom.TunableFactory(
                            description='Randomly selects items based on a weighted list.'
                        ), 
                        tested_items=DefinitionsTested.TunableFactory(
                            description='Test items that are able to be displayed within the picker.'
                            ), 
                        default='all_items'
                    )
                )
            ),
            allow_none=False
        ),
        'add_picker_dialog_categories_to_interactions': TunableList(
            description='A list of purchase picker interactions and picker dialog categories to add.',
            tunable=TunableTuple(
                interactions_to_add_to=TunableList(
                    description='A list of interactions to add to the relationship panel',
                    tunable=TunableReference(
                        description='Reference to an interaction tuning instance',
                        manager=services.affordance_manager(),
                        allow_none=False,
                        pack_safe=True
                    ),
                    allow_none=False,
                    unique_entries=True
                ),
                picker_dialog_categories=TunableList(
                    description='A list of categories that will be displayed in the picker.', 
                    tunable=TunableTuple(
                        description='Tuning for a single category in the picker.', 
                        tag=TunableEnumEntry(
                            description='A single tag used for filtering items. If an item in the picker has this tag then it will be displayed in this category.', 
                            tunable_type=tag.Tag, 
                            default=tag.Tag.INVALID
                        ), 
                        icon=TunableResourceKey(
                            description='Icon that represents this category.', 
                            default=None, 
                            resource_types=sims4.resources.CompoundTypes.IMAGE
                        ), 
                        tooltip=TunableLocalizedString(
                            description='A localized string for the tooltip of the category.'
                        )
                    )
                )
            ),
            allow_none=False
        )
    }

    @classmethod
    def _tuning_loaded_callback(cls):
        logger.info('Processing {}', str(cls))
        try:
            xml_injector.version.request_version(cls.xml_injector_minimum_version, cls.version_error_dialog)
            for entry in cls.add_interactions_to_objects:
                if isinstance(entry.object_selection, str) or entry.object_selection is None:
                    logger.warn('Tuning warning, missing or invalid object_selection')
                else:
                    xml_injector.add_to_tuning.add_super_affordances_to_objects(entry.object_selection,
                                                                                entry._super_affordances)
            if cls.add_interactions_to_sims:
                xml_injector.add_to_tuning.add_super_affordances_to_sims(cls.add_interactions_to_sims)
            if cls.add_interactions_to_phones:
                xml_injector.add_to_tuning.add_super_affordances_to_phones(cls.add_interactions_to_phones)
            if cls.add_interactions_to_relationship_panel:
                xml_injector.add_to_tuning.add_super_affordances_to_relpanel(cls.add_interactions_to_relationship_panel)
            for entry in cls.add_mixer_interactions:
                xml_injector.add_to_tuning.add_mixer_to_affordance_list(entry.mixer_snippets, entry.affordances)
            for entry in cls.add_to_loot_actions:
                if entry.loot_actions_ref is None:
                    logger.warn('Tuning warning, missing or invalid loot_actions_ref')
                else:
                    xml_injector.add_to_tuning.add_to_loot_actions(entry.loot_actions_ref, entry.loot_actions_to_add)
            for entry in cls.add_to_random_loot_actions:
                if entry.random_weighted_loot_ref is None:
                    logger.warn('Tuning warning, missing or invalid random_weighted_loot_ref')
                else:
                    xml_injector.add_to_tuning.add_to_random_loot_actions(entry.random_weighted_loot_ref,
                                                                          entry.random_loot_actions_to_add)
            for entry in cls.add_states_to_objects:
                if isinstance(entry.object_selection, str) or entry.object_selection is None:
                    logger.warn('Tuning warning, missing or invalid object_selection')
                else:
                    xml_injector.add_to_tuning.add_states_to_objects(entry.object_selection, entry.state_component)
            for entry in cls.add_name_component_to_objects:
                if isinstance(entry.object_selection, str) or entry.object_selection is None:
                    logger.warn('Tuning warning, missing or invalid object_selection')
                else:
                    xml_injector.add_to_tuning.add_name_component_to_objects(entry.object_selection,
                                                                             entry.name_component)
            for entry in cls.add_object_relationships_to_objects:
                if isinstance(entry.object_selection, str) or entry.object_selection is None:
                    logger.warn('Tuning warning, missing or invalid object_selection')
                else:
                    xml_injector.add_to_tuning.add_object_relationships_to_objects(entry.object_selection,
                                                                                   entry.object_relationships_component)
            for entry in cls.add_lock_aware_interactions_to_lockable_objects:
                if isinstance(entry.object_selection, str) or entry.object_selection is None:
                    logger.warn('Tuning warning, missing or invalid object_selection')
                else:
                    xml_injector.add_to_tuning.add_lock_aware_interactions_to_lockable_objects(entry.object_selection,
                                                                                entry.super_affordances)
            for entry in cls.add_buffs_to_trait:
                if entry.trait is None:
                    logger.warn('Tuning warning, missing or invalid trait')
                else:
                    xml_injector.add_to_tuning.add_buffs_to_trait(entry.trait, entry.buffs)
            for entry in cls.add_satisfaction_store_rewards:
                if entry.new_items is None:
                    logger.warn('Tuning warning, missing or invalid satisfaction reward')
                else:
                    xml_injector.add_to_tuning.add_satisfaction_store_rewards(entry.new_items)
            for entry in cls.add_purchase_list_options_to_interactions:
                if entry.interactions_to_add_to is None or entry.purchase_list_options is None:
                    logger.warn('Tuning warning, missing or invalid interaction or purchase_list_options')
                else:
                    xml_injector.add_to_tuning.add_purchase_list_options_to_interactions(entry.interactions_to_add_to, entry.purchase_list_options)
            for entry in cls.add_picker_dialog_categories_to_interactions:
                if entry.interactions_to_add_to is None or entry.picker_dialog_categories is None:
                    logger.warn('Tuning warning, missing or invalid interaction or purchase_list_options')
                else:
                    xml_injector.add_to_tuning.add_picker_dialog_categories_to_interactions(entry.interactions_to_add_to, entry.picker_dialog_categories)
        except:
            logger.error('Exception occurred processing XmlInjector tuning instance {}', str(cls))
            logger.error(traceback.format_exc())

    def __repr__(self):
        return '<XmlInjector:({})>'.format(self.__name__)

    def __str__(self):
        return '{}'.format(self.__name__)
